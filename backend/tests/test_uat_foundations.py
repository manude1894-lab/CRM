"""UAT 05-11-2026 (UAT-15): with Set up Foundations, the people are Founders, Council Members, Beneficiaries and Guardians."""
import pytest
from fastapi import HTTPException

from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_party_service as parties, account_service
from tests import flow

UAE = "United Arab Emirates"


def person(role, name="P Person", **kw):
    base = dict(party_role=role, full_name=name, constitution="Individual", country_of_residence=UAE, nationality=UAE,
                mobile_country_code="+971", mobile_number="501234567", email="p@example.com")
    return AccountPartyCreate(**{**base, **kw})


@pytest.fixture()
def foundation(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    for p in list(acc.parties):
        parties.remove_party(db, p.id, "Now a foundation", rm)
    account_service.update_account(db, acc.id, AccountUpdate(services_obtained=["Set up Foundations"]), rm)
    db.refresh(acc)
    return acc, rm


def gaps(acc):
    return [m["label"] for m in account_service.missing_mandatory(acc) if m["field"] == "parties"]


def test_a_foundation_needs_a_founder_not_100_percent(db, foundation):
    acc, rm = foundation
    assert gaps(acc) == ["At least one Founder"]
    parties.create_party(db, acc.id, person("Founder"), rm)
    db.refresh(acc)
    assert gaps(acc) == []


@pytest.mark.parametrize("role", ["Founder", "Council Member", "Beneficiary", "Guardian"])
def test_each_role_has_a_ubos_details(db, foundation, role):
    acc, rm = foundation
    assert parties.create_party(db, acc.id, person(role), rm).party_role == role
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person(role, email=None), rm)
    assert "Contact Email" in e.value.detail


def test_foundation_roles_only_on_a_foundation(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person("Founder"), rm)
    assert "Set up Foundations" in e.value.detail


def test_an_ordinary_company_keeps_the_shareholder_rule(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    for p in list(acc.parties):
        parties.remove_party(db, p.id, "Testing", rm)
    db.refresh(acc)
    assert gaps(acc) == ["At least one Shareholder / UBO"]
