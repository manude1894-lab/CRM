"""P3 — Compliance approvals: client amendments (BRD §13), document removal (§16) and case approval."""
import io
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile

from app.models import Account, AccountParty, ApprovalRequest, AuditLog
from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.schemas.case import CaseCreate, CaseUpdate
from app.schemas import CaseStageChangeRequest  # noqa: F401  (import check)
from app.models.case import CaseStage
from app.services import (account_party_service, account_service, amendment_service as amend,
                          case_approval_service as case_ok, case_service, client_workflow_service as wf,
                          document_service)
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)


def approved_client(db, people):
    acc = complete_client(db, people["maker"])
    wf.submit(db, acc, people["maker"])
    wf.approve(db, acc, people["checker"])
    wf.change_status(db, acc, people["maker"], "activate")
    return acc


# ─── Client amendments ──────────────────────────────────────────────────────

def test_approved_client_needs_explicit_amend(db, people):
    acc = approved_client(db, people)
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(industry="Banking"), people["maker"])
    assert e.value.status_code == 409 and "Amend client" in e.value.detail


def test_amendment_is_staged_until_compliance_approves(db, people, act_as):
    maker, checker = people["maker"], people["checker"]
    acc = approved_client(db, people)
    amend.start(db, acc, maker)
    staged = account_service.update_account(db, acc.id, AccountUpdate(industry="Banking", website="https://x.example"), maker)
    assert staged["industry"] == "Banking"
    db.expire_all()
    assert db.get(Account, acc.id).industry == "Fintech"  # live record untouched

    req = amend.submit(db, acc, maker, "New industry per licence")
    assert req.status == "Pending"
    labels = {c["label"]: (c["old"], c["new"]) for c in req.changes["account"]}
    assert labels["Industry"] == ("Fintech", "Banking")

    # Locked while with Compliance
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(industry="Insurance"), maker)
    assert "awaiting Compliance" in e.value.detail

    act_as(checker)
    amend.approve(db, acc, checker)
    db.expire_all()
    live = db.get(Account, acc.id)
    assert live.industry == "Banking" and live.profile_status == "Active"
    events = db.query(AuditLog).filter(AuditLog.account_id == acc.id).all()
    assert any(e.action == "amend_approve" for e in events)
    assert any(e.action == "update" and e.user_id == checker.id and "industry" in (e.changes or {}) for e in events)


def test_checker_cannot_approve_own_amendment(db, people):
    acc = approved_client(db, people)
    checker = people["checker"]
    amend.start(db, acc, checker)
    account_service.update_account(db, acc.id, AccountUpdate(industry="Banking"), checker)
    amend.submit(db, acc, checker)
    with pytest.raises(HTTPException) as e:
        amend.approve(db, acc, checker)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        amend.approve(db, acc, people["maker"])  # not an approver
    amend.approve(db, acc, people["checker2"])


def test_reject_returns_changes_to_maker_as_draft(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = approved_client(db, people)
    amend.start(db, acc, maker)
    account_service.update_account(db, acc.id, AccountUpdate(industry="Banking"), maker)
    amend.submit(db, acc, maker)
    with pytest.raises(HTTPException):
        amend.reject(db, acc, checker, "Documents missing or incomplete", "too short")
    amend.reject(db, acc, checker, "Documents missing or incomplete", "Upload the new trade licence first please")
    draft = amend.open_request(db, acc.id)
    assert draft.status == "Draft" and draft.maker_id == maker.id
    assert draft.payload["account"]["industry"] == "Banking"
    v = amend.view(db, acc, maker)
    assert v["previous"].reason_text.startswith("Upload the new trade licence")
    assert v["preview"]["account"]["industry"] == "Banking"


def test_staged_party_changes_are_validated_and_not_live(db, people):
    maker = people["maker"]
    acc = approved_client(db, people)
    jane = acc.parties[0]
    amend.start(db, acc, maker)
    account_party_service.update_party(db, jane.id, AccountPartyUpdate(effective_ownership_percent=Decimal("50")), maker)
    with pytest.raises(HTTPException) as e:  # 50 + 60 > 100 is refused while staging, as on a direct save
        account_party_service.create_party(db, acc.id, AccountPartyCreate(
            party_role="Shareholder", full_name="Omar New", mobile_country_code="+971", mobile_number="509999999",
            email="omar@example.com", effective_ownership_percent=Decimal("60")), maker)
    assert "can't exceed 100%" in e.value.detail
    db.expire_all()
    assert db.get(AccountParty, jane.id).effective_ownership_percent == Decimal("100.00")  # live untouched


def test_party_amendment_end_to_end(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = approved_client(db, people)
    jane_id = acc.parties[0].id
    amend.start(db, acc, maker)
    account_party_service.update_party(db, jane_id, AccountPartyUpdate(effective_ownership_percent=Decimal("50")), maker)
    omar = account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Shareholder", full_name="Omar New", mobile_country_code="+971", mobile_number="509999999",
        email="omar@example.com", effective_ownership_percent=Decimal("50")), maker)
    account_party_service.update_party(db, omar["id"], AccountPartyUpdate(full_name="Omar Haddad"), maker, account_id=acc.id)
    listed = account_party_service.list_parties_for(db, acc.id, maker)
    assert sorted(p["full_name"] for p in listed) == ["Jane Owner", "Omar Haddad"]
    assert len(account_party_service.list_parties_for(db, acc.id, checker)) == 1  # others see the live record

    req = amend.submit(db, acc, maker)
    actions = {p["action"]: p["name"] for p in req.changes["parties"]}
    assert actions == {"changed": "Jane Owner", "added": "Omar Haddad"}
    amend.approve(db, acc, checker)
    db.expire_all()
    parties = db.query(AccountParty).filter(AccountParty.account_id == acc.id).all()
    assert sorted((p.full_name, p.effective_ownership_percent) for p in parties) == [
        ("Jane Owner", Decimal("50.00")), ("Omar Haddad", Decimal("50.00"))]


def test_submit_refuses_incomplete_or_empty_amendment(db, people):
    maker = people["maker"]
    acc = approved_client(db, people)
    amend.start(db, acc, maker)
    with pytest.raises(HTTPException) as e:
        amend.submit(db, acc, maker)
    assert "no changes" in e.value.detail
    account_party_service.delete_party(db, acc.parties[0].id, maker)  # removes the only shareholder
    with pytest.raises(HTTPException) as e:
        amend.submit(db, acc, maker)
    assert "incomplete" in e.value.detail and "Shareholder" in e.value.detail


def test_one_amendment_at_a_time(db, people):
    acc = approved_client(db, people)
    amend.start(db, acc, people["maker"])
    with pytest.raises(HTTPException) as e:
        amend.start(db, acc, people["checker2"])
    assert "already amending" in e.value.detail
    with pytest.raises(HTTPException) as e:
        amend.start(db, acc, people["other_rm"])  # can't see the client at all
    assert e.value.status_code == 403
    amend.discard(db, acc, people["maker"])
    amend.start(db, acc, people["maker"])


def test_cannot_amend_before_approval(db, people):
    acc = complete_client(db, people["maker"])
    with pytest.raises(HTTPException):
        amend.start(db, acc, people["maker"])


def test_inbox_lists_amendments(db, people):
    acc = approved_client(db, people)
    amend.start(db, acc, people["maker"])
    account_service.update_account(db, acc.id, AccountUpdate(industry="Banking"), people["maker"])
    assert wf.inbox(db, people["checker"]) == []  # drafts aren't with Compliance yet
    amend.submit(db, acc, people["maker"])
    [r] = wf.inbox(db, people["checker"])
    assert r.request_type == "client_amendment"


# ─── BRD §16 document removal ───────────────────────────────────────────────

def _upload(db, acc, user):
    f = UploadFile(file=io.BytesIO(b"%PDF-1.4 test"), filename="passport.pdf", headers={"content-type": "application/pdf"})
    return document_service.create_for_account(db, acc.id, f, "PASSPORT", user)


def test_document_removal_rules(db, people, seed_master, make_role, make_user):
    seed_master("document_category", ["PASSPORT"])
    maker = people["maker"]
    acc = complete_client(db, maker)
    d1 = _upload(db, acc, maker)
    document_service.delete(db, d1.id, maker)  # not yet submitted: uploader may remove

    d2 = _upload(db, acc, maker)
    wf.submit(db, acc, maker)
    wf.withdraw(db, acc, maker)
    with pytest.raises(HTTPException) as e:
        document_service.delete(db, d2.id, maker)
    assert "only an Approver" in e.value.detail
    deleter = make_user("Dee", business_role=make_role("Doc approver", ["document.delete_submitted"]))
    acc.spoc_id = deleter.id  # give the deleter visibility
    db.commit()
    document_service.delete(db, d2.id, deleter)

    d3 = _upload(db, acc, maker)
    acc.spoc_id = maker.id
    db.commit()
    wf.submit(db, acc, maker)
    wf.approve(db, acc, people["checker"])
    with pytest.raises(HTTPException) as e:
        document_service.delete(db, d3.id, people["checker"])
    assert "no longer be removed" in e.value.detail


# ─── Case approval ──────────────────────────────────────────────────────────

def _case(db, user, **kw):
    return case_service.create_case(db, CaseCreate(company_name="Falcon BVI Ltd", **kw), user)


def test_new_case_waits_for_compliance(db, people):
    maker, checker = people["maker"], people["checker"]
    case = _case(db, maker)
    assert case.compliance_status == "Pending Approval"
    with pytest.raises(HTTPException) as e:
        case_service.change_stage(db, case.id, CaseStage.RM_ASSIGNED, maker)
    assert "awaiting Compliance" in e.value.detail
    with pytest.raises(HTTPException):
        case_service.update_case(db, case.id, CaseUpdate(notes="x"), maker)  # locked
    [r] = wf.inbox(db, checker)
    assert r.request_type == "case_creation"
    with pytest.raises(HTTPException):
        case_ok.approve(db, case, maker)  # not an approver
    case_ok.approve(db, case, checker)
    assert case.compliance_status == "Approved"
    case_service.change_stage(db, case.id, CaseStage.RM_ASSIGNED, maker)


def test_returned_case_is_fixed_and_resubmitted(db, people):
    maker, checker = people["maker"], people["checker"]
    case = _case(db, maker)
    case_ok.reject(db, case, checker, "Documents missing or incomplete", "Client is not onboarded yet, link the client first")
    assert case.compliance_status == "Returned"
    case_service.update_case(db, case.id, CaseUpdate(notes="Linked to the client"), maker)  # direct edit while returned
    assert case.notes == "Linked to the client"
    case_ok.resubmit(db, case, maker)
    assert case.compliance_status == "Pending Approval"
    case_ok.approve(db, case, checker)


def test_edit_to_approved_case_becomes_amendment(db, people):
    maker, checker = people["maker"], people["checker"]
    case = _case(db, maker)
    case_ok.approve(db, case, checker)
    case_service.update_case(db, case.id, CaseUpdate(service_type="Restoration", notes="Client asked"), maker)
    db.expire_all()
    case = case_service.get_case(db, case.id, maker)
    assert case.notes is None  # unchanged until approved
    req = case_ok.pending_request(db, case.id)
    assert req.request_type == "case_amendment"
    assert {c["label"] for c in req.changes["case"]} == {"Service", "Notes"}
    with pytest.raises(HTTPException):
        case_service.update_case(db, case.id, CaseUpdate(notes="again"), maker)  # one at a time
    case_ok.approve(db, case, checker)
    db.expire_all()
    case = case_service.get_case(db, case.id, maker)
    assert case.notes == "Client asked" and case.service_type == "Restoration"


def test_blank_address_blocks_are_not_changes(db, people):
    # The form sends empty address blocks; "no address" and "address with blank lines" are the same.
    maker = people["maker"]
    acc = approved_client(db, people)
    amend.start(db, acc, maker)
    blank = {"line1": "", "line2": "", "landmark": "", "zip": "", "po_box": "", "city": "", "country": ""}
    account_service.update_account(db, acc.id, AccountUpdate(industry="Banking", registered_address=blank), maker)
    req = amend.submit(db, acc, maker)
    assert [c["field"] for c in req.changes["account"]] == ["industry"]
