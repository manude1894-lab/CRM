"""Servicing (BRD §15): Visit / Call Reports and service requests on the client, SMS."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Activity, Instruction, Invoice, Notification
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.services import activity_service, instruction_service, notification_service, sms_service


def visit(**kw):
    base = dict(activity_date=date(2026, 10, 5), activity_type="Visit Report", status="Completed",
                summary="Discussed renewal of the trade licence", client_contact="Omar Haddad", location="Client office, JLT")
    base.update(kw)
    return ActivityCreate(**base)


# ─── Visit / Call Reports on the client ─────────────────────────────────────

def test_visit_report_on_client(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Falcon Trading LLC", spoc=rm, profile_status="Active")
    act = activity_service.create_activity(db, visit(account_id=acc.id), rm)
    assert act.account_id == acc.id and act.company_name == "Falcon Trading LLC"
    items, total = activity_service.list_activities(db, rm, account_id=acc.id)
    assert total == 1 and items[0].activity_type.value == "Visit Report"


def test_report_templates_require_their_fields(db, make_user, make_account):
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active")
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(account_id=acc.id, location=None), rm)
    assert "Location" in e.value.detail
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(account_id=acc.id, activity_type="Call Report", client_contact=""), rm)
    assert "Client contact spoken to" in e.value.detail
    call = activity_service.create_activity(db, visit(account_id=acc.id, activity_type="Call Report", location=None), rm)
    with pytest.raises(HTTPException):
        activity_service.update_activity(db, call.id, ActivityUpdate(client_contact=""), rm)


def test_activity_needs_a_client_and_access(db, make_user, make_account):
    rm, other = make_user("Rita"), make_user("Otto")
    acc = make_account(spoc=rm, profile_status="Active")
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(), rm)
    assert "Choose the client" in e.value.detail
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(account_id=acc.id), other)
    assert e.value.status_code == 403


def test_anchor_rm_sees_colleagues_reports_on_their_client(db, make_user, make_account, make_role):
    anchor, colleague, stranger = make_user("Anchor"), make_user("Colleague"), make_user("Stranger")
    acc = make_account(spoc=anchor, non_anchor=[colleague], profile_status="Active")
    activity_service.create_activity(db, visit(account_id=acc.id), colleague)
    assert activity_service.list_activities(db, anchor, account_id=acc.id)[1] == 1
    assert activity_service.list_activities(db, stranger)[1] == 0


# ─── Client-level service requests ──────────────────────────────────────────

def test_service_request_on_client(db, make_user, make_account, seed_master):
    seed_master("service_request_type", ["Change of Address", "AR Filing"])
    rm = make_user()
    acc = make_account(name="Falcon Trading LLC", spoc=rm, profile_status="Active")
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Address",
                                                                      charge_amount=Decimal("500")), rm)
    assert sr.account_id == acc.id
    with pytest.raises(HTTPException):
        instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Made up"), rm)
    # BRD §16: completing a charged request is an instruction to Accounts to invoice the client.
    instruction_service.update_instruction(db, sr.id, InstructionUpdate(status="Completed"), rm)
    [inv] = db.query(Invoice).all()
    assert (inv.account_id, inv.status, inv.amount) == (acc.id, "Requested", Decimal("500"))
    items, total = instruction_service.list_instructions(db, rm, search="Falcon")
    assert total == 1


def test_service_request_visibility(db, make_user, make_account):
    rm, stranger = make_user("Rita"), make_user("Stranger")
    acc = make_account(spoc=rm, profile_status="Active")
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Other", other_description="Courier documents"), rm)
    assert instruction_service.list_instructions(db, stranger)[1] == 0
    with pytest.raises(HTTPException):
        instruction_service.get_instruction(db, sr.id, stranger)


@pytest.mark.parametrize("raw,expected", [("+971 50 123 4567", "+971501234567"), ("00971501234567", "+971501234567"),
                                          ("0501234567", None), ("", None), (None, None)])
def test_sms_number_normalisation(raw, expected):
    assert sms_service.normalise(raw) == expected


def test_sms_sent_only_for_chosen_types(db, make_user, monkeypatch):
    sent = []
    monkeypatch.setattr(notification_service, "send_sms", lambda to, text: sent.append((to, text)))
    u = make_user("Mia MLRO")
    u.mobile = "+971501234567"
    db.commit()
    notification_service.notify_user(db, u.id, "Rita submitted client X for approval.", "client_submitted")
    notification_service.notify_user(db, u.id, "Prospect assigned to you", "prospect_assigned")
    assert sent == [("+971501234567", "TRIAM: Rita submitted client X for approval.")]
    assert db.query(Notification).filter(Notification.user_id == u.id).count() == 2


def test_sms_disabled_by_default_never_raises():
    assert sms_service.send_sms("+971501234567", "hello") is False


def test_service_requests_open_once_the_client_is_approved(db, make_user, make_account, seed_master):
    """BRD §8: once approved, the client is available for service requests."""
    seed_master("service_request_type", ["Change of Address"])
    rm = make_user()
    acc = make_account(name="Still Onboarding Ltd", spoc=rm, profile_status="WIP")
    with pytest.raises(HTTPException) as e:
        instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Address"), rm)
    assert "once the client is approved" in e.value.detail
