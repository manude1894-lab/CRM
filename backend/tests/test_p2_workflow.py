"""P2 — maker-checker and client lifecycle (BRD §11, §12 steps 10–14, §14, §15)."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import UserRole, AccountParty, AuditLog, ApprovalRequest, Notification
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_service, account_party_service, client_workflow_service as wf, document_service


@pytest.fixture()
def people(make_user, make_role, seed_master):
    seed_master("rejection_reason", ["Documents missing or incomplete"])
    checker_role = make_role("MLRO", ["client.approve"])
    return {
        "maker": make_user("Rita RM"),
        "checker": make_user("Mia MLRO", business_role=checker_role),
        "checker2": make_user("Carl CO", business_role=checker_role),
        "other_rm": make_user("Otto RM"),
    }


def complete_client(db, maker):
    """A Corporate client with every BRD mandatory field filled in."""
    acc = account_service.create_account(db, AccountCreate(
        company_name="Complete Co", industry="Fintech", anchor_entity="TCPL", spoc_id=maker.id,
        country="United Arab Emirates", registration_number="CI-123", incorporation_date=date(2020, 1, 1),
        license_number="L-1", licensing_authority="DMCC", license_start_date=date(2024, 1, 1),
        license_expiry_date=date(2030, 1, 1), license_activities="Consulting", financial_year_end="12-31",
        services_obtained=["Accounting & Bookkeeping"], risk_rating="Low", aml_classification="Standard",
        kyc_verified_by="Rita RM", cdd_completion_date=date(2026, 9, 1),
    ), maker)
    account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Shareholder", full_name="Jane Owner", mobile_country_code="+971", mobile_number="501234567",
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

    wf.submit(db, acc, maker, "Ready for review")
    assert acc.profile_status == "Awaiting Approval"
    req = wf.pending_request(db, acc.id)
    assert req.maker_id == maker.id and req.snapshot["account"]["company_name"] == "Complete Co"
    assert len(req.snapshot["parties"]) == 1

    wf.approve(db, acc, checker, "All documents verified")
    assert acc.profile_status == "Approved" and req.status == "Approved" and req.checker_id == checker.id

    wf.change_status(db, acc, maker, "activate")
    assert acc.profile_status == "Active"
    wf.change_status(db, acc, checker, "deactivate", "Client paused services")
    wf.change_status(db, acc, checker, "reactivate")
    wf.change_status(db, acc, maker, "mark_exit", "Client moving to another provider")
    assert acc.profile_status == "Marked for Exit"
    wf.change_status(db, acc, checker, "confirm_exit")
    assert acc.profile_status == "Exited"

    actions = [e.action for e in db.query(AuditLog).filter(AuditLog.account_id == acc.id, AuditLog.subject_type == "Account").all()]
    for a in ("submit", "approve", "activate", "deactivate", "reactivate", "mark_exit", "confirm_exit"):
        assert a in actions


# ─── Maker-checker rules ────────────────────────────────────────────────────

def test_submit_blocked_until_mandatory_fields_complete(db, people):
    acc = account_service.create_account(db, AccountCreate(company_name="Half Done", industry="x", anchor_entity="TCPL"), people["maker"])
    with pytest.raises(HTTPException) as e:
        wf.submit(db, acc, people["maker"])
    assert e.value.status_code == 400 and "mandatory field" in e.value.detail


def test_maker_cannot_approve_own_submission_even_as_approver(db, people):
    checker = people["checker"]
    acc = complete_client(db, checker)
    wf.submit(db, acc, checker)
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, checker)
    assert e.value.status_code == 403 and "another approver" in e.value.detail
    wf.approve(db, acc, people["checker2"])  # a different approver can
    assert acc.profile_status == "Approved"


def test_ordinary_rm_cannot_approve(db, people):
    acc = complete_client(db, people["maker"])
    wf.submit(db, acc, people["maker"])
    with pytest.raises(HTTPException) as e:
        wf.approve(db, acc, people["other_rm"])  # can't even see the client
    assert e.value.status_code == 403


def test_reject_needs_listed_reason_and_meaningful_text(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    wf.submit(db, acc, maker)
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
    wf.submit(db, acc, maker)
    assert acc.profile_status == "Awaiting Approval"


def test_profile_locked_while_awaiting_approval(db, people):
    maker = people["maker"]
    acc = complete_client(db, maker)
    wf.submit(db, acc, maker)
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
    wf.submit(db, acc, maker)
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
    wf.submit(db, acc, people["maker"])
    notified = {n.user_id for n in db.query(Notification).filter(Notification.notification_type == "client_submitted").all()}
    assert notified == {people["checker"].id, people["checker2"].id}


def test_status_actions_need_permission_and_reasons(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    wf.submit(db, acc, maker)
    wf.approve(db, acc, checker)
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
    wf.submit(db, acc, maker); wf.approve(db, acc, checker); wf.change_status(db, acc, maker, "activate")
    wf.change_status(db, acc, maker, "mark_exit", "Leaving"); wf.change_status(db, acc, checker, "confirm_exit")
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(industry="x"), checker)
    assert e.value.status_code == 409


def test_allowed_actions_explain_why(db, people):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    assert codes(db, acc, maker) == {"submit": True}
    wf.submit(db, acc, maker)
    assert codes(db, acc, maker) == {"approve": False, "reject": False, "withdraw": True}
    assert codes(db, acc, checker) == {"approve": True, "reject": True, "withdraw": True}
    reasons = {a["action"]: a["reason"] for a in wf.allowed_actions(db, acc, maker)}
    assert "approver" in reasons["approve"]


def test_inbox_lists_pending_requests_the_checker_can_see(db, people):
    acc = complete_client(db, people["maker"])
    wf.submit(db, acc, people["maker"])
    [r] = wf.inbox(db, people["checker"])
    assert r.account_id == acc.id
