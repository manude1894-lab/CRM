"""UAT 04-11-2026 (UAT-02): a new client can't be submitted without at least one supporting document.
Retest 09/10-11-2026: each person or entity on the client needs a document of their own too."""
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.models import Document
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_party_service, account_service, amendment_service as amend, client_workflow_service as wf
from tests import flow


def _without_documents(db, acc, people_too=True):
    q = db.query(Document).filter(Document.account_id == acc.id)
    (q if people_too else q.filter(Document.party_id.is_(None))).delete()
    db.commit()
    db.refresh(acc)
    return acc


def labels(acc):
    return [m["label"] for m in account_service.missing_mandatory(acc)]


def test_corporate_client_needs_a_document(db, real_user):
    rm = real_user("Rel. Manager")
    acc = _without_documents(db, flow.complete_client(db, rm), people_too=False)
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


def test_a_persons_document_does_not_stand_in_for_the_client(db, real_user):
    rm = real_user("Rel. Manager")
    acc = _without_documents(db, flow.complete_client(db, rm), people_too=False)
    assert labels(acc) == ["At least one supporting document"]


def _person(db, acc, rm, name, role="Director", **extra):
    return account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role=role, full_name=name, residential_address={"line1": "1 Main Street", "city": "Dubai"}, country_of_incorp_or_birth="India", country_of_residence="India", nationality="India",
        mobile_country_code="+91", mobile_number="501234567", email="p@example.com", **extra), rm)


def test_each_person_needs_their_own_document(db, real_user):
    """The tester's case: a UBO saved without documents held up nothing."""
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    omar = _person(db, acc, rm, "Omar Saeed", "Authorised Signatory")
    db.refresh(acc)
    assert labels(acc) == ["A document for Omar Saeed (Authorised Signatory)"]
    with pytest.raises(HTTPException):
        flow.submit(db, acc, rm)
    flow.add_document(db, acc, rm, party_id=omar.id)
    db.refresh(acc)
    assert labels(acc) == []


def test_ubo_without_documents_is_listed(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    jane = acc.parties[0]
    db.query(Document).filter(Document.party_id == jane.id).delete()
    db.commit()
    db.refresh(acc)
    assert labels(acc) == ["A document for Jane Owner (Shareholder)"]


def test_one_person_in_two_roles_needs_one_document(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)  # Jane Owner, Shareholder, with her passport
    _person(db, acc, rm, " jane owner ")  # the same person as Director
    db.refresh(acc)
    assert labels(acc) == []


def test_an_entity_shareholder_needs_one_too(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    _person(db, acc, rm, "C Ltd", "Shareholder", constitution="Entity")
    db.refresh(acc)
    assert labels(acc) == ["A document for C Ltd (Shareholder)"]


def test_a_person_can_be_saved_before_their_documents(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    assert _person(db, acc, rm, "Layla Haddad").id  # only Submit asks for the document


def test_a_person_added_by_amendment_is_not_held_up(db, real_user):
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver")
    acc = flow.approved_client(db, {"maker": rm, "checker": mlro, "approver": approver})
    amend.start(db, acc, rm)
    _person(db, acc, rm, "New Director")
    assert amend.submit(db, acc, rm, "New director appointed").status == "Pending"


@pytest.mark.parametrize("fields", [{"removed_at": datetime(2026, 11, 1, tzinfo=timezone.utc)}], ids=["removed"])
def test_a_removed_document_does_not_count(db, real_user, fields):
    rm = real_user("Rel. Manager")
    acc = _without_documents(db, flow.complete_client(db, rm), people_too=False)
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
