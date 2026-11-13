"""UAT 05-11-2026 (UAT-15): with Set up Foundations, the people are Founders, Council Members, Beneficiaries and Guardians."""
import pytest
from fastapi import HTTPException

from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_party_service as parties, account_service
from tests import flow

UAE = "United Arab Emirates"


def person(role, name="P Person", **kw):
    base = dict(party_role=role, full_name=name, constitution="Individual", residential_address={"line1": "1 Main Street", "city": "Dubai"}, country_of_incorp_or_birth="India", country_of_residence=UAE, nationality=UAE,
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


def test_a_foundation_needs_a_founder_and_two_council_members_not_100_percent(db, foundation):
    """Triam UAT 10-11-2026: at least two Council Members, checked at Submit (they're entered one at a time)."""
    acc, rm = foundation
    assert gaps(acc) == ["At least one Founder", "At least 2 Council Members (currently 0)"]
    parties.create_party(db, acc.id, person("Founder"), rm)
    parties.create_party(db, acc.id, person("Council Member", full_name="Council One"), rm)
    db.refresh(acc)
    assert gaps(acc) == ["At least 2 Council Members (currently 1)"]
    parties.create_party(db, acc.id, person("Council Member", full_name="Council Two"), rm)
    db.refresh(acc)
    assert gaps(acc) == []


@pytest.mark.parametrize("role", ["Founder", "Council Member", "Beneficiary", "Guardian"])
def test_each_role_has_a_ubos_details(db, foundation, role):
    acc, rm = foundation
    assert parties.create_party(db, acc.id, person(role), rm).party_role == role
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person(role, email=None), rm)
    assert "Contact Email" in e.value.detail
    # Like a UBO, an individual needs a Country of Birth; an entity doesn't.
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person(role, full_name="No Birth", country_of_incorp_or_birth=None), rm)
    assert "Country of Birth" in e.value.detail
    assert parties.create_party(db, acc.id, person(role, full_name="Holding Co", constitution="Entity",
                                                   country_of_incorp_or_birth=None, nationality=None), rm).id


def test_foundation_people_have_no_shareholding_percentage(db, foundation):
    """Triam UAT: "Shareholding % should not come" for a foundation's people."""
    acc, rm = foundation
    for role in ("Founder", "Council Member", "Council Member", "Beneficiary", "Guardian"):
        parties.create_party(db, acc.id, person(role, full_name=f"{role} {len(acc.parties)}"), rm)
        db.refresh(acc)
    assert not any("100" in g or "%" in g for g in gaps(acc))


def test_shareholders_from_before_must_go_before_submit(db, real_user):
    """A company that becomes a foundation keeps its old Shareholder / Director records on screen; Submit
    asks for them to be removed, so the foundation's people replace them."""
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    account_service.update_account(db, acc.id, AccountUpdate(services_obtained=["Set up Foundations"]), rm)
    parties.create_party(db, acc.id, person("Founder"), rm)
    for n in ("One", "Two"):
        parties.create_party(db, acc.id, person("Council Member", full_name=f"Council {n}"), rm)
    db.refresh(acc)
    leftover = [g for g in gaps(acc) if g.startswith("Remove the")]
    assert leftover and "Shareholder" in leftover[0]
    for p in [p for p in acc.parties if p.party_role in ("Shareholder", "Director")]:
        parties.remove_party(db, p.id, "Now a foundation", rm)
    db.refresh(acc)
    assert gaps(acc) == []


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
