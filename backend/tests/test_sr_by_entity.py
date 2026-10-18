"""Service requests by Triam entity (Triam's "Service Requests – Triam Entities" list)."""
import pytest
from fastapi import HTTPException

from app.models import MasterItem
from app.schemas.instruction import InstructionCreate, InstructionUpdate
from app.services import instruction_service as sr


@pytest.fixture()
def lists(db):
    """A slice of Triam's list: TABL / IFZA types and statuses, TBVI's own, Other for all."""
    rows = [("triam_entity", e, None) for e in ("TABL", "IFZA", "TBVI")]
    rows += [("service_request_type", "Financial Audit", ["TABL"]), ("service_request_type", "VAT Registration", ["IFZA"]),
             ("service_request_type", "Transfer IN", ["TBVI"]), ("service_request_type", "Other", None)]
    rows += [("service_request_status", s, ["TABL", "IFZA"]) for s in ("Received", "Applied for service")]
    rows += [("service_request_status", s, ["TBVI"]) for s in ("Not started", "Pending with Vistra")]
    rows += [("service_request_status", s, None) for s in ("On Hold", "Completed", "Dropped")]
    for i, (lt, code, ents) in enumerate(rows):
        meta = {"entities": ents} if ents else {}
        if code in ("Completed", "Dropped"):
            meta["closed"] = True
        db.add(MasterItem(list_type=lt, code=code, label=code, sort_order=i, is_active=True, meta=meta or None))
    db.commit()


def test_options_follow_the_entity(db, lists):
    tabl = sr.options(db, "TABL")
    assert tabl["types"] == ["Financial Audit", "Other"]
    assert [s["code"] for s in tabl["statuses"]] == ["Received", "Applied for service", "On Hold", "Completed", "Dropped"]
    tbvi = sr.options(db, "TBVI")
    assert tbvi["types"] == ["Transfer IN", "Other"] and tbvi["statuses"][0]["code"] == "Not started"


def test_request_uses_the_clients_entity_and_its_lists(db, lists, make_user, make_account):
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active", anchor_entity="TABL", non_anchor_entities=["IFZA"])
    a = sr.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Financial Audit"), rm)
    assert a.triam_entity == "TABL" and a.status == "Received"  # anchor entity, its first status
    b = sr.create_instruction(db, InstructionCreate(account_id=acc.id, triam_entity="IFZA", instruction_type="VAT Registration"), rm)
    assert b.triam_entity == "IFZA"
    with pytest.raises(HTTPException) as e:  # a TABL type under IFZA
        sr.create_instruction(db, InstructionCreate(account_id=acc.id, triam_entity="IFZA", instruction_type="Financial Audit"), rm)
    assert "not a request type for IFZA" in e.value.detail
    with pytest.raises(HTTPException) as e:  # an entity that doesn't serve the client
        sr.create_instruction(db, InstructionCreate(account_id=acc.id, triam_entity="TBVI", instruction_type="Transfer IN"), rm)
    assert "doesn't serve" in e.value.detail
    with pytest.raises(HTTPException):  # TBVI's status on a TABL request
        sr.update_instruction(db, a.id, InstructionUpdate(status="Pending with Vistra"), rm)
    sr.update_instruction(db, a.id, InstructionUpdate(status="Applied for service"), rm)
    with pytest.raises(HTTPException):  # Dropped only through Cancel, with a reason
        sr.update_instruction(db, a.id, InstructionUpdate(status="Dropped"), rm)


def test_other_needs_a_short_description(db, lists, make_user, make_account):
    rm = make_user()
    acc = make_account(spoc=rm, profile_status="Active", anchor_entity="TABL")
    with pytest.raises(HTTPException):
        sr.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Other"), rm)
    with pytest.raises(Exception):  # over 50 characters
        InstructionCreate(account_id=acc.id, instruction_type="Other", other_description="x" * 51)
    r = sr.create_instruction(db, InstructionCreate(account_id=acc.id, instruction_type="Other", other_description=" Courier the COI "), rm)
    assert r.other_description == "Courier the COI"
    r2 = sr.update_instruction(db, r.id, InstructionUpdate(instruction_type="Financial Audit"), rm)
    assert r2.other_description is None
