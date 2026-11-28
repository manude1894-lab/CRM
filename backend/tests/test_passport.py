"""Triam 20-11-2026: Passport Number and a passport copy are required at Submit for an individual client and for
every individual person on a client (UBO, Director, Signatory, Joint Holder, Founder, ...). An entity is not asked."""
from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.account import AccountCreate, AccountImportRow, AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_party_service, account_service, standard_reports_service as rpt
from tests import flow
from tests.helpers import rows_of


def labels(acc):
    return [m["label"] for m in account_service.missing_mandatory(acc)]


def _person(db, acc, rm, name, role="Director", **extra):
    return account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role=role, full_name=name, residential_address={"line1": "1 Main Street", "city": "Dubai"},
        country_of_incorp_or_birth="India", country_of_residence="India", nationality="India",
        mobile_country_code="+91", mobile_number="9876543210", email="p@example.com", **extra), rm)


@pytest.mark.parametrize("raw, saved", [("n 123-4567", "N1234567"), ("a1b2c3d4e5f6", "A1B2C3D4E5F6"), ("", None)])
def test_passport_number_is_tidied(raw, saved):
    assert AccountPartyCreate(party_role="Director", full_name="X", passport_number=raw).passport_number == saved
    assert AccountUpdate(passport_number=raw).passport_number == saved


@pytest.mark.parametrize("raw", ["AB12", "A1234567890123", "AB/1234!"])
def test_passport_number_format_is_checked(raw):
    with pytest.raises(ValidationError):
        AccountPartyUpdate(passport_number=raw)
    with pytest.raises(ValidationError):
        AccountCreate(company_name="X", passport_number=raw)


def test_individual_client_needs_its_passport_number_and_copy(db, real_user):
    rm = real_user("Rel. Manager")
    acc = account_service.create_account(db, AccountCreate(company_name="Rahul Verma", account_type="Individual",
                                                           anchor_entity="TCPL", spoc_id=rm.id), rm)
    assert {"Passport Number", "Passport copy of the client"} <= set(labels(acc))
    account_service.update_account(db, acc.id, AccountUpdate(passport_number="z9876543"), rm)
    flow.add_document(db, acc, rm, category="PASSPORT", filename="passport.pdf")
    db.refresh(acc)
    assert acc.passport_number == "Z9876543"
    assert not {"Passport Number", "Passport copy of the client"} & set(labels(acc))


def test_each_individual_person_gives_number_expiry_and_copy(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    omar = _person(db, acc, rm, "Omar Saeed")
    db.refresh(acc)
    assert labels(acc) == ["Passport Number of Omar Saeed (Director)", "Passport Expiry of Omar Saeed (Director)",
                           "Passport copy for Omar Saeed (Director)"]
    with pytest.raises(HTTPException):
        flow.submit(db, acc, rm)
    account_party_service.update_party(db, omar.id, AccountPartyUpdate(**flow.PASSPORT), rm, account_id=acc.id)
    flow.add_document(db, acc, rm, party_id=omar.id, category="PASSPORT")
    db.refresh(acc)
    assert labels(acc) == []
    assert flow.submit(db, acc, rm).status == "Pending"


def test_one_person_in_two_roles_gives_the_passport_once(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)  # Jane Owner, Shareholder, with her passport
    acc.parties[0].dob_or_incorp_date = date(1985, 3, 1)
    db.commit()
    _person(db, acc, rm, "Jane Owner", dob_or_incorp_date=date(1985, 3, 1))  # the same person as Director, no passport typed
    db.refresh(acc)
    assert labels(acc) == []


def test_an_entity_needs_no_passport(db, real_user):
    rm = real_user("Rel. Manager")
    acc = flow.complete_client(db, rm)
    c = _person(db, acc, rm, "C Ltd", "Shareholder", constitution="Entity")
    flow.add_document(db, acc, rm, party_id=c.id)  # its incorporation certificate, any category
    db.refresh(acc)
    assert labels(acc) == []


def test_import_tidies_the_passport_number_and_refuses_a_bad_one(db, make_user):
    from app.models import Account
    admin = make_user("Ada", role="admin")
    results = account_service.import_accounts(db, admin, [
        AccountImportRow(company_name="Good Person", account_type="Individual", anchor_entity="TCPL", passport_number="n 123-4567"),
        AccountImportRow(company_name="Bad Person", account_type="Individual", anchor_entity="TCPL", passport_number="AB!"),
    ], dry_run=False)
    assert [r.status for r in results] == ["ok", "error"] and "Passport Number" in results[1].message
    assert db.query(Account).filter(Account.company_name == "Good Person").one().passport_number == "N1234567"


def test_expiry_reports_show_the_passport_number(db, make_user, make_account):
    from datetime import timedelta
    rm = make_user("Rita RM")
    make_account(name="Rahul Verma", spoc=rm, account_type="Individual", passport_number="Z9876543",
                 passport_expiry_date=rpt._today() + timedelta(days=10))
    [row] = rows_of(rpt.documents_expiring(db, rm))
    assert (row["Doc Type"], row["Doc No."]) == ("Passport", "Z9876543")
