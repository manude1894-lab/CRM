"""UAT 06-11-2026 (UAT-20): only individual shareholders count towards 100%; an entity's percentage is
suppressed. The examples are Triam's own, from the "UBO Percentage computation" sheet."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import AccountParty
from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_party_service as parties, account_service, amendment_service as amend
from app.services import client_workflow_service as wf
from tests import flow

UAE = "United Arab Emirates"
INDIVIDUAL, ENTITY = "Individual", "Entity"
EXAMPLE_1 = [("A", INDIVIDUAL, "25"), ("B", INDIVIDUAL, "25"), ("C Ltd", ENTITY, None), ("C1", INDIVIDUAL, "30"), ("C2", INDIVIDUAL, "20")]
EXAMPLE_2 = [("Z", INDIVIDUAL, "20"), ("X Ltd", ENTITY, None), ("X1", INDIVIDUAL, "20"), ("X2", INDIVIDUAL, "10"), ("Y Ltd", ENTITY, None),
             ("Y1", INDIVIDUAL, "20"), ("Y2", INDIVIDUAL, "25"), ("Y3", INDIVIDUAL, "5")]


def shareholder(name, constitution=INDIVIDUAL, pct=None):
    return AccountPartyCreate(party_role="Shareholder", full_name=name, constitution=constitution, country_of_residence=UAE, nationality=UAE,
                              mobile_country_code="+971", mobile_number="501234567", email="p@example.com",
                              effective_ownership_percent=Decimal(pct) if pct else None)


@pytest.fixture()
def empty_client(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    for p in list(acc.parties):
        parties.remove_party(db, p.id, "Replacing the shareholders", rm)
    db.refresh(acc)
    return acc, rm


def ownership_gaps(acc):
    return [m["label"] for m in account_service.missing_mandatory(acc) if m["field"] == "parties"]


@pytest.mark.parametrize("structure", [EXAMPLE_1, EXAMPLE_2], ids=["ABC Ltd", "Zee Ltd"])
def test_triams_examples_add_up_to_100(db, empty_client, structure):
    acc, rm = empty_client
    for name, constitution, pct in structure:
        parties.create_party(db, acc.id, shareholder(name, constitution, pct), rm)
    db.refresh(acc)
    assert ownership_gaps(acc) == []


def test_an_entitys_percentage_counts_for_nothing_and_is_cleared(db, empty_client):
    acc, rm = empty_client
    for name, pct in (("A", "25"), ("B", "25")):
        parties.create_party(db, acc.id, shareholder(name, INDIVIDUAL, pct), rm)
    entity = parties.create_party(db, acc.id, shareholder("C Ltd", ENTITY, "50"), rm)
    db.refresh(acc)
    assert entity.effective_ownership_percent is None
    assert ownership_gaps(acc) == ["Individual shareholding must total 100% (currently 50.00%)"]


def test_changing_an_individual_to_an_entity_clears_the_percentage(db, empty_client):
    acc, rm = empty_client
    p = parties.create_party(db, acc.id, shareholder("Was A Person", INDIVIDUAL, "40"), rm)
    assert parties.update_party(db, p.id, AccountPartyUpdate(constitution=ENTITY), rm).effective_ownership_percent is None


def test_individuals_can_not_pass_100_but_an_entity_can_be_added_at_100(db, empty_client):
    acc, rm = empty_client
    parties.create_party(db, acc.id, shareholder("A", INDIVIDUAL, "100"), rm)
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, shareholder("B", INDIVIDUAL, "1"), rm)
    assert "101" in e.value.detail
    assert parties.create_party(db, acc.id, shareholder("C Ltd", ENTITY), rm)


def test_an_individual_still_needs_a_percentage(db, empty_client):
    acc, rm = empty_client
    with pytest.raises(HTTPException):
        parties.create_party(db, acc.id, shareholder("No Share"), rm)


def test_only_entities_can_not_be_submitted(db, empty_client):
    acc, rm = empty_client
    parties.create_party(db, acc.id, shareholder("C Ltd", ENTITY), rm)
    db.refresh(acc)
    assert ownership_gaps(acc) == ["Individual shareholding must total 100% (currently 0%)"]


def _approved_with_old_entity_share(db, real_user):
    """A client approved under the old rule: A 50% and C Ltd 50% added up to 100%."""
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver")
    acc = flow.complete_client(db, rm)
    for p in list(acc.parties):
        parties.remove_party(db, p.id, "Replacing the shareholders", rm)
    db.refresh(acc)
    parties.create_party(db, acc.id, shareholder("A", INDIVIDUAL, "100"), rm)
    db.refresh(acc)
    flow.submit(db, acc, rm)
    flow.approve_all(db, acc, mlro, approver)
    wf.change_status(db, acc, rm, "activate")
    a = db.query(AccountParty).filter(AccountParty.account_id == acc.id, AccountParty.full_name == "A").one()
    a.effective_ownership_percent = Decimal("50")
    db.add(AccountParty(account_id=acc.id, party_role="Shareholder", full_name="C Ltd", constitution=ENTITY, effective_ownership_percent=Decimal("50")))
    db.commit()
    db.refresh(acc)
    return acc, rm


def test_old_client_can_still_get_an_unrelated_amendment(db, real_user):
    acc, rm = _approved_with_old_entity_share(db, real_user)
    assert ownership_gaps(acc)  # a gap under today's rule
    amend.start(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(license_activities="Amended activities"), rm)
    assert amend.submit(db, acc, rm, "Licence activities changed").status == "Pending"


def test_an_amendment_can_not_create_a_new_gap(db, real_user):
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver")
    acc = flow.approved_client(db, {"maker": rm, "checker": mlro, "approver": approver})
    amend.start(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(contact_email=""), rm)
    with pytest.raises(HTTPException) as e:
        amend.submit(db, acc, rm, "Removing the contact email")
    assert "Contact Email" in e.value.detail
