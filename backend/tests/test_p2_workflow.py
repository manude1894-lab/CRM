"""P2 — maker-checker and client lifecycle (BRD §11, §12 steps 10–14, §14, §15)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import UserRole, AccountParty, AuditLog, ApprovalRequest, Notification
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_service, account_party_service, client_workflow_service as wf, document_service
from tests import flow


@pytest.fixture()
def people(make_user, make_role, seed_master):
    seed_master("rejection_reason", ["Documents missing or incomplete"])
    checker_role = make_role("MLRO", ["client.approve"])
    return {
        "maker": make_user("Rita RM"),
        "checker": make_user("Mia MLRO", business_role=checker_role),
        "checker2": make_user("Carl CO", business_role=checker_role),
        "other_rm": make_user("Otto RM"),
        "approver": make_user("Ada Approver", business_role=make_role("Approver", ["client.final_approve"])),
    }


def complete_client(db, maker):
    """A Corporate client with every BRD mandatory field filled in."""
    acc = account_service.create_account(db, AccountCreate(
        company_name="Complete Co", industry="Fintech", anchor_entity="TCPL", spoc_id=maker.id,
        country="United Arab Emirates", registration_number="CI-123", incorporation_date=date(2020, 1, 1),
        license_number="L-1", licensing_authority="DMCC", license_start_date=date(2024, 1, 1),
        license_expiry_date=date(2030, 1, 1), license_activities="Consulting", financial_year_end="12-31",
        services_obtained=["Accounting & Bookkeeping"], client_category="Existing",
        contact_mobile_country_code="+971", contact_mobile_number="43334444", contact_email="info@complete.example",
        nature_of_services_sought=["Accounting & Bookkeeping"],
        registered_address={"line1": "Office 1201, Tower A", "city": "Dubai", "country": "United Arab Emirates"},
        operating_address={"line1": "Office 1201, Tower A", "city": "Dubai", "country": "United Arab Emirates"},
        is_regulated=False, corp_tax_registered=False, has_introducer=False,
    ), maker)
    account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Shareholder", country_of_residence="United Arab Emirates", nationality="United Arab Emirates", full_name="Jane Owner", mobile_country_code="+971", mobile_number="501234567",
        email="jane@example.com", effective_ownership_percent=Decimal("100"),
    ), maker)
    db.refresh(acc)
    assert account_service.missing_mandatory(acc) == []
    return acc


def codes(db, acc, user):
    return {a["action"]: a["allowed"] for a in wf.allowed_actions(db, acc, user)}


# ─── Happy path ─────────────────────────────────────────────────────────────

def test_full_lifecycle(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    assert acc.profile_status == "WIP"  # creation = New, adding the shareholder moved it to WIP

    flow.submit(db, acc, maker, "Ready for review")
    assert acc.profile_status == "Awaiting Approval"
    req = wf.pending_request(db, acc.id)
    assert req.maker_id == maker.id and req.snapshot["account"]["company_name"] == "Complete Co"
    assert len(req.snapshot["parties"]) == 1

    assert acc.client_id is None  # temporary ID until Compliance approves
    assert req.stage == "Compliance" and req.kyc_declared and req.maker_comment == "Ready for review"
    flow.fill_cdd(db, acc, checker)
    wf.approve(db, acc, checker, "All documents verified")
    assert acc.profile_status == "Awaiting Approval" and req.stage == "Approver"
    assert acc.client_id == "TCPL/00001" and req.compliance_checker_id == checker.id
    wf.approve(db, acc, people["approver"], "Approved for onboarding")
    assert acc.profile_status == "Approved" and req.status == "Approved" and req.checker_id == people["approver"].id

    wf.change_status(db, acc, maker, "activate")
    assert acc.profile_status == "Active"
    wf.change_status(db, acc, checker, "deactivate", "Client paused services")
    wf.change_status(db, acc, checker, "reactivate")
    wf.change_status(db, acc, maker, "mark_exit", "Client moving to another provider")
    assert acc.profile_status == "Marked for Exit"
    wf.change_status(db, acc, checker, "confirm_exit")
    assert acc.profile_status == "Exited"

    actions = [e.action for e in db.query(AuditLog).filter(AuditLog.account_id == acc.id, AuditLog.subject_type == "Account").all()]
    for a in ("submit", "cdd_update", "compliance_approve", "approve", "activate", "deactivate", "reactivate", "mark_exit", "confirm_exit"):
        assert a in actions


# ─── Maker-checker rules ────────────────────────────────────────────────────

def test_submit_blocked_until_mandatory_fields_complete(db, people):
    acc = account_service.create_account(db, AccountCreate(company_name="Half Done", industry="x", anchor_entity="TCPL"), people["maker"])
    with pytest.raises(HTTPException) as e:
        flow.submit(db, acc, people["maker"])
    assert e.value.status_code == 400 and "mandatory field" in e.value.detail


def test_maker_cannot_approve_own_submission_even_as_approver(db, people):
    checker = people["checker"]
    acc = complete_client(db, checker)
    flow.submit(db, acc, checker)
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, checker)
    assert e.value.status_code == 403 and "someone else" in e.value.detail
    flow.approve_all(db, acc, people["checker2"], people["approver"])  # a different checker can
    assert acc.profile_status == "Approved"


def test_ordinary_rm_cannot_approve(db, people):
    acc = complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, people["other_rm"])  # can't even see the client
    assert e.value.status_code == 403


def test_reject_needs_listed_reason_and_meaningful_text(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    with pytest.raises(HTTPException):
        wf.reject(db, acc, checker, "Documents missing or incomplete", "bad")  # too short
    with pytest.raises(HTTPException):
        wf.reject(db, acc, checker, "Not a real reason", "The passport copy for Jane is expired, please re-upload")
    wf.reject(db, acc, checker, "Documents missing or incomplete", "The passport copy for Jane is expired, please re-upload")
    assert acc.profile_status == "WIP"
    req = db.query(ApprovalRequest).filter(ApprovalRequest.account_id == acc.id).one()
    assert req.status == "Rejected" and req.reason_code == "Documents missing or incomplete"
    # The maker is told why.
    note = db.query(Notification).filter(Notification.user_id == maker.id, Notification.notification_type == "client_rejected").one()
    assert "passport copy" in note.message
    # And can resubmit after fixing.
    flow.submit(db, acc, maker)
    assert acc.profile_status == "Awaiting Approval"


def test_profile_locked_while_awaiting_approval(db, people):
    maker = people["maker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(industry="Changed"), maker)
    assert e.value.status_code == 409
    with pytest.raises(HTTPException):
        account_party_service.create_party(db, acc.id, AccountPartyCreate(party_role="Director", full_name="New Dir"), maker)
    with pytest.raises(HTTPException) as e:
        document_service.create_for_account(db, acc.id, None, "PASSPORT", maker)  # lock is checked before the file is read
    assert e.value.status_code == 409
    # Withdraw unlocks it.
    wf.withdraw(db, acc, maker)
    account_service.update_account(db, acc.id, AccountUpdate(industry="Changed"), maker)
    assert acc.industry == "Changed"


def test_withdraw_only_by_submitter_or_approver(db, people, make_user):
    maker = people["maker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    # A supervisor can see the client but is neither the submitter nor an approver.
    boss = make_user("Boss")
    maker.supervisor_id = boss.id
    db.commit()
    with pytest.raises(HTTPException) as e:
        wf.withdraw(db, acc, boss)
    assert e.value.status_code == 403
    wf.withdraw(db, acc, people["checker"])  # an approver can
    assert acc.profile_status == "WIP"


def test_approvers_are_notified_on_submit(db, people):
    acc = complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    notified = {n.user_id for n in db.query(Notification).filter(Notification.notification_type == "client_submitted").all()}
    assert notified == {people["checker"].id, people["checker2"].id}


def test_status_actions_need_permission_and_reasons(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    flow.approve_all(db, acc, checker, people["approver"])
    with pytest.raises(HTTPException) as e:
        wf.change_status(db, acc, maker, "deactivate", "x")  # not Active yet
    assert e.value.status_code == 409
    wf.change_status(db, acc, maker, "activate")
    with pytest.raises(HTTPException) as e:
        wf.change_status(db, acc, maker, "deactivate", "pause")  # needs an approver
    assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        wf.change_status(db, acc, maker, "mark_exit")  # reason required
    wf.change_status(db, acc, checker, "mark_exit", "Client leaving")
    with pytest.raises(HTTPException) as e:
        wf.change_status(db, acc, checker, "confirm_exit")  # same person who marked it
    assert "Another approver" in e.value.detail
    wf.change_status(db, acc, maker, "cancel_exit")
    assert acc.profile_status == "Active"


def test_exited_client_is_read_only(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker); flow.approve_all(db, acc, checker, people["approver"]); wf.change_status(db, acc, maker, "activate")
    wf.change_status(db, acc, maker, "mark_exit", "Leaving"); wf.change_status(db, acc, checker, "confirm_exit")
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(industry="x"), checker)
    assert e.value.status_code == 409


def test_allowed_actions_explain_why(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    assert codes(db, acc, maker) == {"submit": True}
    flow.submit(db, acc, maker)
    assert codes(db, acc, maker) == {"approve": False, "reject": False, "withdraw": True}
    reasons = {a["action"]: a["reason"] for a in wf.allowed_actions(db, acc, maker)}
    assert "Compliance" in reasons["approve"]
    # Compliance can't approve until the CDD section is complete
    assert codes(db, acc, checker) == {"approve": False, "reject": True, "withdraw": True}
    assert "CDD section" in {a["action"]: a["reason"] for a in wf.allowed_actions(db, acc, checker)}["approve"]
    flow.fill_cdd(db, acc, checker)
    assert codes(db, acc, checker) == {"approve": True, "reject": True, "withdraw": True}
    wf.approve(db, acc, checker, "CDD done")
    # now with the Approver
    assert codes(db, acc, checker) == {"approve": False, "reject": False}
    assert codes(db, acc, people["approver"]) == {"approve": True, "reject": True}


def test_inbox_lists_pending_requests_the_checker_can_see(db, people):
    acc = complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    [r] = wf.inbox(db, people["checker"])
    assert r.account_id == acc.id
    assert wf.inbox(db, people["approver"]) == []  # not yet at the Approver step
    flow.compliance_approve(db, acc, people["checker"])
    [r] = wf.inbox(db, people["approver"])
    assert r.account_id == acc.id and r.stage == "Approver"


# ─── Three-level approval (Triam BRD mark-up §7–§10) ────────────────────────

def test_submit_needs_comments_and_kyc_declaration(db, people):
    maker = people["maker"]
    acc = complete_client(db, maker)
    with pytest.raises(HTTPException) as e:
        wf.submit(db, acc, maker, "", True)
    assert "RM/Sales comments" in e.value.detail
    with pytest.raises(HTTPException) as e:
        wf.submit(db, acc, maker, "word " * 251, True)
    assert "250 words" in e.value.detail
    with pytest.raises(HTTPException) as e:
        wf.submit(db, acc, maker, "All checked", False)
    assert "KYC verification" in e.value.detail
    wf.submit(db, acc, maker, "All checked", True)
    assert acc.profile_status == "Awaiting Approval"


def test_only_compliance_completes_the_cdd_section(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(risk_rating="Low"), maker)
    assert e.value.status_code == 403 and "Compliance" in e.value.detail
    flow.submit(db, acc, maker)
    # the profile is locked, but Compliance can still complete the CDD section …
    flow.fill_cdd(db, acc, checker, risk="High")
    assert acc.risk_rating == "High" and acc.next_aml_review_date is not None
    # … and nothing else
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(industry="Changed"), checker)
    assert e.value.status_code == 409


def test_compliance_and_approver_comments_are_mandatory(db, people):
    maker, checker, approver = people["maker"], people["checker"], people["approver"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    flow.fill_cdd(db, acc, checker)
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, checker, "  ")
    assert "Compliance comments" in e.value.detail
    wf.approve(db, acc, checker, "CDD complete")
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, approver, None)
    assert "Approver's comments" in e.value.detail


def test_approver_can_reject_back_to_the_rm(db, people):
    maker, checker, approver = people["maker"], people["checker"], people["approver"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    flow.compliance_approve(db, acc, checker)
    wf.reject(db, acc, approver, "Documents missing or incomplete", "The engagement letter has not been signed yet")
    assert acc.profile_status == "WIP"
    note = db.query(Notification).filter(Notification.user_id == maker.id, Notification.notification_type == "client_rejected").one()
    assert "engagement letter" in note.message
    assert acc.client_id == "TCPL/00001"  # already issued at the Compliance step; kept


def test_compliance_cannot_give_final_approval_without_the_approver_role(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    flow.compliance_approve(db, acc, checker)
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, people["checker2"], "Looks fine")
    assert e.value.status_code == 403 and "Approver" in e.value.detail
