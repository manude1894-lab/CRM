"""UAT 04-11-2026 (UAT-02): a new client can't be submitted without at least one supporting document."""
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.models import Document
from app.schemas.account import AccountCreate, AccountUpdate
from app.services import account_service, amendment_service as amend, client_workflow_service as wf
from tests import flow


def _without_documents(db, acc):
    db.query(Document).filter(Document.account_id == acc.id).delete()
    db.commit()
    db.refresh(acc)
    return acc


def labels(acc):
    return [m["label"] for m in account_service.missing_mandatory(acc)]


def test_corporate_client_needs_a_document(db, real_user):
    rm = real_user("Rel. Manager")
    acc = _without_documents(db, flow.complete_client(db, rm))
    assert labels(acc) == ["At least one supporting document"]
    with pytest.raises(HTTPException) as e:
        flow.submit(db, acc, rm)
    assert e.value.status_code == 400
    flow.add_document(db, acc, rm)
    db.refresh(acc)
    assert flow.submit(db, acc, rm).status == "Pending"


def test_individual_client_needs_one_too(db, real_user):
    rm = real_user("Rel. Manager")
    acc = account_service.create_account(db, AccountCreate(company_name="Rahul Verma", account_type="Individual", anchor_entity="TCPL", spoc_id=rm.id), rm)
    assert "At least one supporting document" in labels(acc)
    flow.add_document(db, acc, rm)
    db.refresh(acc)
    assert "At least one supporting document" not in labels(acc)


def test_a_persons_document_counts(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    party = acc.parties[0]
    _without_documents(db, acc)
    flow.add_document(db, acc, rm, party_id=party.id)
    db.refresh(acc)
    assert labels(acc) == []


@pytest.mark.parametrize("fields", [{"removed_at": datetime(2026, 11, 1, tzinfo=timezone.utc)}], ids=["removed"])
def test_a_removed_document_does_not_count(db, real_user, fields):
    rm = real_user("Rel. Manager")
    acc = _without_documents(db, flow.complete_client(db, rm))
    flow.add_document(db, acc, rm, **fields)
    db.refresh(acc)
    assert labels(acc) == ["At least one supporting document"]


def test_client_approved_before_the_rule_stays_amendable(db, real_user):
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver")
    acc = flow.approved_client(db, {"maker": rm, "checker": mlro, "approver": approver})
    _without_documents(db, acc)
    amend.start(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(license_expiry_date=date(2031, 1, 1)), rm)
    assert amend.submit(db, acc, rm, "Licence renewed").status == "Pending"


def test_rejected_client_also_needs_one_to_resubmit(db, real_user, seed_master):
    seed_master("rejection_reason", ["Documents missing or incomplete"])
    rm, mlro = real_user("Rel. Manager"), real_user("MLRO")
    acc = flow.complete_client(db, rm)
    flow.submit(db, acc, rm)
    wf.reject(db, acc, mlro, "Documents missing or incomplete", "The licence copy is unreadable, please re-upload")
    _without_documents(db, acc)
    assert {a["action"]: a["allowed"] for a in wf.allowed_actions(db, acc, rm)}["submit"] is False
