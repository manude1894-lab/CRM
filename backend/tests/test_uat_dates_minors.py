"""Triam 16-11-2026: tax number format, licence and other date rules, and minors."""
from datetime import date, timedelta

import pytest
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.account import AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_party_service as parties, account_service
from tests import flow

TODAY = date.today()
UAE = "United Arab Emirates"


def years_ago(n, days=0):
    return TODAY - relativedelta(years=n) - timedelta(days=days)


def rejects(db, acc, user, msg, **fields):
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(**fields), user)
    assert msg in e.value.detail
    db.rollback()


def test_tax_numbers_take_letters_and_digits():
    assert AccountUpdate(trn_vat_number=" gb123456789 ").trn_vat_number == "GB123456789"
    for bad in ("GB 123", "123-456", "12345678901234567890X"):
        with pytest.raises(ValidationError):
            AccountUpdate(trn_vat_number=bad)


def test_a_uae_number_is_15_digits(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)  # registered in the UAE
    rejects(db, acc, rm, "a UAE number is 15 digits", trn_vat_number="GB123456789")
    rejects(db, acc, rm, "a UAE number is 15 digits", corp_tax_registration_number="12345")
    account_service.update_account(db, acc.id, AccountUpdate(trn_vat_number="100123456700003"), rm)
    account_service.update_account(db, acc.id, AccountUpdate(country="United Kingdom", trn_vat_number="GB123456789"), rm)


def test_licence_dates(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)  # incorporated 2020-01-01, licence 2024-01-01 to 2030-01-01
    rejects(db, acc, rm, "License Start Date cannot be in the future", license_start_date=TODAY + timedelta(days=1))
    rejects(db, acc, rm, "cannot be before the Incorporation Date", license_start_date=date(2019, 12, 31))
    rejects(db, acc, rm, "must be after the License Start Date", license_start_date=TODAY, license_expiry_date=TODAY)
    rejects(db, acc, rm, "License Expiry Date cannot be before today", license_expiry_date=TODAY - timedelta(days=1))
    account_service.update_account(db, acc.id, AccountUpdate(license_start_date=TODAY, license_expiry_date=TODAY + timedelta(days=365)), rm)


def test_other_expiry_dates(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    # Triam UAT 27-11-2026: a past Engagement Letter date is accepted, for existing and new clients.
    account_service.update_account(db, acc.id, AccountUpdate(engagement_letter_signed=True,
                                                             engagement_letter_valid_until=TODAY - timedelta(days=400)), rm)
    rejects(db, acc, rm, "LEI Expiry Date cannot be before today", lei_expiry_date=TODAY - timedelta(days=1))
    rejects(db, acc, rm, "Current regulatory license expiry cannot be before today", regulatory_license_expiry_date=TODAY - timedelta(days=1))


def test_an_old_date_on_record_doesnt_block_other_saves(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    acc.license_expiry_date = TODAY - timedelta(days=5)  # expired since it was entered
    db.commit()
    account_service.update_account(db, acc.id, AccountUpdate(license_expiry_date=acc.license_expiry_date, nature_of_business="Trading"), rm)


def test_an_individual_client_is_an_adult(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    acc.account_type = "Individual"
    db.commit()
    rejects(db, acc, rm, "must be at least 18 years old", date_of_birth=years_ago(18) + timedelta(days=1))
    rejects(db, acc, rm, "cannot be in the future", date_of_birth=TODAY + timedelta(days=1))
    rejects(db, acc, rm, "more than 120 years ago", date_of_birth=years_ago(121))
    rejects(db, acc, rm, "Passport Expiry Date must be after the Date of Birth", date_of_birth=years_ago(30), passport_expiry_date=years_ago(31))
    account_service.update_account(db, acc.id, AccountUpdate(date_of_birth=years_ago(18)), rm)


def person(role, dob, **kw):
    base = dict(party_role=role, full_name=f"{role} Child", constitution="Individual", dob_or_incorp_date=dob,
                residential_address={"line1": "1 Main Street", "city": "Dubai"}, country_of_incorp_or_birth="India",
                country_of_residence=UAE, nationality=UAE, mobile_country_code="+971", mobile_number="501234567",
                email="p@example.com")
    return AccountPartyCreate(**{**base, **kw})


def test_a_minor_shareholder_needs_a_guardian(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    [owner] = [p for p in acc.parties if p.party_role == "Shareholder"]
    parties.update_party(db, owner.id, AccountPartyUpdate(effective_ownership_percent=90), rm)
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person("Shareholder", years_ago(10), effective_ownership_percent=0.01), rm)
    assert "is a minor" in e.value.detail and "Parent / Guardian Name" in e.value.detail
    db.rollback()
    p = parties.create_party(db, acc.id, person("Shareholder", years_ago(10), effective_ownership_percent=0.01,
                                                guardian_name="Jane Owner", guardian_relationship="Mother"), rm)
    assert p.guardian_name == "Jane Owner"
    # Once they're an adult (a corrected date of birth), the guardian details are dropped.
    p = parties.update_party(db, p.id, AccountPartyUpdate(dob_or_incorp_date=years_ago(30)), rm)
    assert p.guardian_name is None


@pytest.mark.parametrize("role", ["Director", "Authorised Signatory"])
def test_roles_acting_for_the_client_must_be_adults(db, people, role):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person(role, years_ago(17)), rm)
    assert "must be at least 18 years old" in e.value.detail


def test_an_entity_isnt_incorporated_in_the_future(db, people):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    with pytest.raises(HTTPException) as e:
        parties.create_party(db, acc.id, person("Shareholder", TODAY + timedelta(days=1), constitution="Entity",
                                                full_name="Holding Co", nationality=None), rm)
    assert "Date of Incorporation cannot be in the future" in e.value.detail
