"""Triam UAT retest 09/10-11-2026: items reopened or added after the first round of fixes."""
import pytest
from pydantic import ValidationError

from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate
from app.services import account_party_service, account_service, document_service
from tests import flow


def test_reason_for_edd_takes_250_characters():
    assert len(AccountUpdate(edd_reason="x" * 250).edd_reason) == 250
    with pytest.raises(ValidationError):
        AccountUpdate(edd_reason="x" * 251)


def test_folder_says_which_parties_are_entities(db, real_user):
    """The form offers company documents (incorporation, licence, MoA) for an entity shareholder."""
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Shareholder", full_name="C Ltd", constitution="Entity", country_of_residence="India",
        residential_address={"line1": "1 Main Street", "city": "Mumbai"},
        mobile_country_code="+91", mobile_number="501234567", email="c@example.com"), rm)
    folder = document_service.client_folder(db, acc.id, rm)
    assert {p["name"]: p["constitution"] for p in folder["parties"]} == {
        "Jane Owner (Shareholder)": "Individual", "C Ltd (Shareholder)": "Entity"}


def test_a_persons_city_is_needed_to_submit(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    jane = acc.parties[0]
    jane.residential_address = {"line1": "Villa 12, Street 4"}
    db.commit()
    db.refresh(acc)
    assert [m["label"] for m in account_service.missing_mandatory(acc)] == [
        "Residential Address of Jane Owner (Shareholder): line 1 and city"]
