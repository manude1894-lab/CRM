"""P5 — servicing (BRD §17): client-linked Visit / Call Reports, client-level service requests, SMS."""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Activity, Instruction, Invoice, Notification
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.schemas.case import CaseCreate
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.services import activity_service, case_service, instruction_service, notification_service, sms_service


def visit(**kw):
    base = dict(activity_date=date(2026, 10, 5), activity_type="Visit Report", status="Completed",
                summary="Discussed renewal of the trade licence", client_contact="Omar Haddad", location="Client office, JLT")
    base.update(kw)
    return ActivityCreate(**base)


# ─── Visit / Call Reports on the client ─────────────────────────────────────

def test_visit_report_on_client_without_case(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Falcon Trading LLC", spoc=rm)
    act = activity_service.create_activity(db, visit(account_id=acc.id), rm)
    assert act.account_id == acc.id and act.case_id is None and act.company_name == "Falcon Trading LLC"
    items, total = activity_service.list_activities(db, rm, account_id=acc.id)
    assert total == 1 and items[0].activity_type.value == "Visit Report"


def test_report_templates_require_their_fields(db, make_user, make_account):
    rm = make_user()
    acc = make_account(spoc=rm)
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(account_id=acc.id, location=None), rm)
    assert "Location" in e.value.detail
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(account_id=acc.id, activity_type="Call Report", client_contact=""), rm)
    assert "Client contact spoken to" in e.value.detail
    call = activity_service.create_activity(db, visit(account_id=acc.id, activity_type="Call Report", location=None), rm)
    with pytest.raises(HTTPException):
        activity_service.update_activity(db, call.id, ActivityUpdate(client_contact=""), rm)


def test_activity_needs_a_client_or_case_and_access(db, make_user, make_account):
    rm, other = make_user("Rita"), make_user("Otto")
    acc = make_account(spoc=rm)
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(), rm)
    assert "Choose the client" in e.value.detail
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(account_id=acc.id), other)
    assert e.value.status_code == 403


def test_case_activity_is_filed_against_its_client(db, make_user, make_account):
    rm = make_user()
    acc = make_account(name="Nova Holdings", spoc=rm)
    case = case_service.create_case(db, CaseCreate(company_name="Nova BVI", account_id=acc.id, rm_id=rm.id), rm)
    act = activity_service.create_activity(db, visit(case_id=case.id, activity_type="Call Report", location=None), rm)
    assert act.account_id == acc.id
    other = make_account(name="Other Co", spoc=rm)
    with pytest.raises(HTTPException) as e:
        activity_service.create_activity(db, visit(case_id=case.id, account_id=other.id), rm)
    assert "different client" in e.value.detail


def test_anchor_rm_sees_colleagues_reports_on_their_client(db, make_user, make_account, make_role):
    anchor, colleague, stranger = make_user("Anchor"), make_user("Colleague"), make_user("Stranger")
    acc = make_account(spoc=anchor, non_anchor=[colleague])
    activity_service.create_activity(db, visit(account_id=acc.id), colleague)
    assert activity_service.list_activities(db, anchor, account_id=acc.id)[1] == 1
    assert activity_service.list_activities(db, stranger)[1] == 0


# ─── Client-level service requests ──────────────────────────────────────────

def test_service_request_for_client_without_case(db, make_user, make_account, seed_master):
    seed_master("service_request_type", ["Change of Address", "AR Filing"])
    rm = make_user()
    acc = make_account(name="Falcon Trading LLC", spoc=rm)
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Change of Address",
                                                                      charge_amount=Decimal("500")), rm)
    assert sr.account_id == acc.id and sr.case_id is None
    with pytest.raises(HTTPException):
        instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Made up"), rm)
    # Completing a charged request without a case doesn't try to create a case invoice.
    instruction_service.update_instruction(db, sr.id, InstructionUpdate(status="Completed"), rm)
    assert db.query(Invoice).count() == 0
    items, total = instruction_service.list_instructions(db, rm, search="Falcon")
    assert total == 1


def test_service_request_visibility(db, make_user, make_account):
    rm, stranger = make_user("Rita"), make_user("Stranger")
    acc = make_account(spoc=rm)
    sr = instruction_service.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Other"), rm)
    assert instruction_service.list_instructions(db, stranger)[1] == 0
    with pytest.raises(HTTPException):
        instruction_service.get_instruction(db, sr.id, stranger)


def test_case_service_request_still_invoices(db, make_user, make_account):
    rm = make_user()
    acc = make_account(spoc=rm)
    case = case_service.create_case(db, CaseCreate(company_name="BVI Co", account_id=acc.id, rm_id=rm.id), rm)
    sr = instruction_service.create_instruction(db, InstructionCreate(case_id=case.id, instruction_type="AR Filing",
                                                                      charge_amount=Decimal("750")), rm)
    assert sr.account_id == acc.id
    instruction_service.update_instruction(db, sr.id, InstructionUpdate(status="Completed"), rm)
    assert db.query(Invoice).filter(Invoice.case_id == case.id).count() == 1


# ─── SMS adapter ────────────────────────────────────────────────────────────

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
    notification_service.notify_user(db, u.id, "Case moved stage", "case_stage_changed")
    assert sent == [("+971501234567", "TRIAM: Rita submitted client X for approval.")]
    assert db.query(Notification).filter(Notification.user_id == u.id).count() == 2


def test_sms_disabled_by_default_never_raises():
    assert sms_service.send_sms("+971501234567", "hello") is False
