"""Triam UAT 13-11-2026 row 79 (Oakbridge, TCPL/00024): two Shareholders both named "Daniel", no date of birth,
one document. They were taken for one person, so the case was submitted with a UBO who had no document."""
from datetime import date
from types import SimpleNamespace as P

from app.models import AccountParty
from app.services import account_service
from tests import flow

DOB = date(1980, 5, 1)


def test_two_shareholders_with_the_same_name_are_two_people(db, people):
    acc = flow.complete_client(db, people["maker"])  # Jane Owner, Shareholder, with a document
    jane = acc.parties[0]
    jane.full_name, jane.dob_or_incorp_date = "Daniel", None
    second = AccountParty(account_id=acc.id, party_role="Shareholder", constitution="Individual", full_name="Daniel")
    db.add(second)
    db.commit()
    db.refresh(acc)
    [missing] = account_service.people_without_documents(acc)
    assert [r.id for r in missing] == [second.id]


def test_one_person_in_two_roles_still_needs_one_document():
    ubo = P(id=1, party_role="Shareholder", full_name="Daniel Smith", dob_or_incorp_date=DOB)
    director = P(id=2, party_role="Director", full_name="daniel smith ", dob_or_incorp_date=DOB)
    assert account_service.group_people([ubo, director]) == [[ubo, director]]


def test_a_blank_date_of_birth_is_not_a_match():
    ubo = P(id=1, party_role="Shareholder", full_name="Daniel", dob_or_incorp_date=None)
    director = P(id=2, party_role="Director", full_name="Daniel", dob_or_incorp_date=None)
    assert len(account_service.group_people([ubo, director])) == 2
