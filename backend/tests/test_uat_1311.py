"""Triam UAT 12/13-11-2026: approval date on approved clients, removing a wrong document on a rejected case,
the registry / government fee on a service request, and the shorter list of prospect statuses."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models import Invoice, ProspectStatus
from app.schemas.instruction import InstructionCreate
from app.schemas.prospect import ProspectUpdate
from app.services import client_workflow_service as wf, document_service, instruction_service as sr
from tests import flow


def test_final_approval_stamps_the_approval_date(db, people):
    acc = flow.complete_client(db, people["maker"])
    flow.submit(db, acc, people["maker"])
    flow.compliance_approve(db, acc, people["checker"])
    db.refresh(acc)
    assert acc.approved_at is None  # Compliance approval alone isn't the client's approval
    req = wf.approve(db, acc, people["approver"], "Final approval given")
    db.refresh(acc)
    assert acc.approved_at == req.decided_at


def test_rm_removes_a_wrong_document_on_a_rejected_case(db, people):
    rm, other = people["maker"], people["other_rm"]
    acc = flow.complete_client(db, rm)
    wrong = flow.add_document(db, acc, rm, filename="wrong-passport.pdf")
    flow.submit(db, acc, rm)
    with pytest.raises(HTTPException):  # with Compliance: nothing changes
        document_service.delete(db, wrong.id, rm, "Wrong file")
    wf.reject(db, acc, people["checker"], "Documents missing or incomplete", "Passport copy is of another person")
    db.refresh(acc)
    assert acc.profile_status == "Rejected"
    someone_elses = flow.add_document(db, acc, other, filename="other.pdf")
    document_service.delete(db, wrong.id, rm, "Wrong passport uploaded")
    db.refresh(wrong)
    assert wrong.removed_at is not None and wrong.removed_reason == "Wrong passport uploaded"
    with pytest.raises(HTTPException):  # only the uploader (or Admin) removes it
        document_service.delete(db, someone_elses.id, rm, "Not mine")


def test_government_fee_has_a_currency_and_reaches_the_accountant(db, people, make_user, make_role, seed_master):
    seed_master("triam_entity", ["TCPL"])
    seed_master("service_request_type", ["Financial Audit"])
    make_user("Ann Accounts", business_role=make_role("Accountant", ["invoice.manage", "view.all_clients"]))
    acc = flow.approved_client(db, people)
    req = sr.create_instruction(db, InstructionCreate(
        account_id=acc.id, instruction_type="Financial Audit", triam_entity="TCPL",
        charge_amount=Decimal("1000"), charge_currency="USD", govt_authority_amount=Decimal("250")), people["maker"])
    assert req.govt_authority_currency == "USD"
    inv = db.get(Invoice, sr.submit_instruction(db, req.id, people["maker"]).invoice_id)
    assert "Payable to Reg./Govt Auth: USD 250" in inv.notes


def test_prospect_statuses_are_new_won_dropped():
    assert [s.value for s in ProspectStatus] == ["New", "Won", "Dropped"]
    for gone in ("Proposal Sent", "Negotiating", "Lost"):
        with pytest.raises(ValidationError):
            ProspectUpdate(status=gone)


def test_migration_revision_ids_fit_alembic_version_column():
    """alembic_version.version_num is VARCHAR(32): a longer revision id fails the deploy."""
    import re
    from pathlib import Path
    for f in (Path(__file__).resolve().parents[1] / "alembic" / "versions").glob("*.py"):
        m = re.search(r'^revision = "([^"]+)"', f.read_text(encoding="utf-8"), re.M)
        assert m and len(m.group(1)) <= 32, f"{f.name}: revision id longer than 32 characters"
