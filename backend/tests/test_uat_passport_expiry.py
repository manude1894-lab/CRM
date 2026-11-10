"""UAT 05-11-2026 (UAT-09): a passport is accepted up to 30 days past its expiry, not more."""
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.models import AccountParty
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_party_service as parties, account_service, amendment_service as amend
from tests import flow

UAE = "United Arab Emirates"


def days_ago(n):
    return date.today() - timedelta(days=n)


def director(expiry, constitution="Individual"):
    return AccountPartyCreate(party_role="Director", full_name="D Person", constitution=constitution, residential_address={"line1": "1 Main Street", "city": "Dubai"}, country_of_incorp_or_birth="India", mobile_country_code="+971", mobile_number="501234567", email="p@example.com", country_of_residence=UAE,
                              nationality=UAE, id_or_license_expiry=expiry)


@pytest.fixture()
def individual(db, real_user):
    rm = real_user("Rel. Manager")
    return account_service.create_account(db, AccountCreate(company_name="Rahul Verma", account_type="Individual", anchor_entity="TCPL", spoc_id=rm.id), rm), rm


@pytest.mark.parametrize("age, accepted", [(0, True), (1, True), (30, True), (31, False), (3650, False), (-400, True)])
def test_client_passport(db, individual, age, accepted):
    acc, rm = individual
    update = AccountUpdate(passport_expiry_date=days_ago(age))
    if accepted:
        account_service.update_account(db, acc.id, update, rm)
    else:
        with pytest.raises(HTTPException) as e:
            account_service.update_account(db, acc.id, update, rm)
        assert e.value.status_code == 400 and "more than 30 days" in e.value.detail


def test_party_passport(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    with pytest.raises(HTTPException):
        parties.create_party(db, acc.id, director(days_ago(31)), rm)
    p = parties.create_party(db, acc.id, director(days_ago(30)), rm)
    with pytest.raises(HTTPException):
        parties.update_party(db, p.id, AccountPartyUpdate(id_or_license_expiry=days_ago(90)), rm)


def test_an_entitys_expired_licence_is_not_a_passport(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    assert parties.create_party(db, acc.id, director(days_ago(400), "Entity"), rm)


def test_passport_that_aged_while_in_draft_blocks_submit(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    db.add(AccountParty(account_id=acc.id, party_role="Director", full_name="Old Passport", constitution="Individual", id_or_license_expiry=days_ago(200)))
    db.commit()
    db.refresh(acc)
    assert {"section": "Shareholder / UBO Information", "field": "parties",
            "label": "The passport of Old Passport expired more than 30 days ago"} in account_service.missing_mandatory(acc)


def test_old_date_on_record_does_not_block_other_edits(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    p = AccountParty(account_id=acc.id, party_role="Director", country_of_incorp_or_birth="India", mobile_country_code="+971", mobile_number="501234567", email="p@example.com", full_name="Old Passport", constitution="Individual",
                     residential_address={"line1": "1 Main Street", "city": "Dubai"}, country_of_residence=UAE, nationality=UAE, id_or_license_expiry=days_ago(200))
    db.add(p)
    db.commit()
    assert parties.update_party(db, p.id, AccountPartyUpdate(nationality="India"), rm).nationality == "India"


def test_approved_client_with_an_old_passport_stays_amendable(db, real_user):
    rm, mlro, approver = real_user("Rel. Manager"), real_user("MLRO"), real_user("Approver")
    acc = flow.approved_client(db, {"maker": rm, "checker": mlro, "approver": approver})
    db.add(AccountParty(account_id=acc.id, party_role="Director", country_of_incorp_or_birth="India", mobile_country_code="+971", mobile_number="501234567", email="p@example.com", full_name="Old Passport", constitution="Individual",
                        residential_address={"line1": "1 Main Street", "city": "Dubai"}, country_of_residence=UAE, nationality=UAE, id_or_license_expiry=days_ago(200)))
    db.commit()
    db.refresh(acc)
    amend.start(db, acc, rm)
    account_service.update_account(db, acc.id, AccountUpdate(license_activities="Amended activities"), rm)
    assert amend.submit(db, acc, rm, "Unrelated change").status == "Pending"
