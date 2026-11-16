"""Triam "CRM one-time service - changes 14-11-2026": Services Obtained removed, and the one-time service rules."""
import pytest

from app.models import Account, MasterItem
from app.schemas.account import AccountUpdate
from app.services import account_service
from tests import flow


@pytest.fixture()
def one_time_table(db):
    """Triam's example: services offered by entities, and the entities for which each is a one-time service."""
    for code, entities, one_time in (
        ("Corporate Tax Registration", ["TABL", "IFZA"], ["TABL"]),
        ("Other Corporate Services", ["IFZA", "TCPL"], ["TMCL", "IFZA", "TCPL"]),
        ("Audit Services", ["TMCL", "TABL", "TCPL"], None),
    ):
        meta = {"entities": entities, **({"one_time_entities": one_time} if one_time else {})}
        db.add(MasterItem(list_type="service", code=code, label=code, sort_order=0, is_active=True, meta=meta))
    db.add(MasterItem(list_type="service", code="Accounting & Bookkeeping", label="Accounting & Bookkeeping", sort_order=0, is_active=True))
    db.commit()


def labels(acc, field):
    return [m["label"] for m in account_service.missing_mandatory(acc) if m["field"] == field]


def test_services_obtained_is_gone():
    assert not hasattr(Account, "services_obtained")
    assert "services_obtained" not in AccountUpdate.model_fields


def test_asked_of_existing_companies_and_individuals_only(db, people):
    acc = flow.complete_client(db, people["maker"])
    assert account_service.asks_one_time(acc)
    account_service.update_account(db, acc.id, AccountUpdate(is_one_time_service=None), people["maker"])
    db.refresh(acc)
    assert labels(acc, "is_one_time_service") == ["Is this a one-time service? (Yes / No)"]  # mandatory
    account_service.update_account(db, acc.id, AccountUpdate(is_one_time_service=True), people["maker"])
    # Under Formation: the question doesn't open, so the answer is cleared.
    account_service.update_account(db, acc.id, AccountUpdate(client_category="Under Formation"), people["maker"])
    db.refresh(acc)
    assert acc.is_one_time_service is None and labels(acc, "is_one_time_service") == []
    assert account_service.asks_one_time(Account(account_type="Individual"))


def test_a_one_time_client_takes_only_one_time_services_of_its_entities(db, people, one_time_table):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)  # TCPL, Accounting & Bookkeeping
    account_service.update_account(db, acc.id, AccountUpdate(is_one_time_service=True), rm)
    db.refresh(acc)
    problems = labels(acc, "nature_of_services_sought")
    assert len(problems) == 1 and "'Accounting & Bookkeeping' is not a one-time service" in problems[0]
    # Corporate Tax Registration is one-time only for TABL, not for this TCPL client.
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_services_sought=["Corporate Tax Registration"]), rm)
    db.refresh(acc)
    assert labels(acc, "nature_of_services_sought")
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_services_sought=["Other Corporate Services"]), rm)
    db.refresh(acc)
    assert labels(acc, "nature_of_services_sought") == [] and labels(acc, "anchor_entity") == []


def test_no_other_entities_for_a_one_time_client(db, people, one_time_table):
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    account_service.update_account(db, acc.id, AccountUpdate(is_one_time_service=True, non_anchor_entities=["TCDL"],
                                                             nature_of_services_sought=["Other Corporate Services"]), rm)
    db.refresh(acc)
    [problem] = labels(acc, "non_anchor_entities")
    assert problem.startswith("TCDL does not offer one-time services") and "IFZA, TABL, TCPL, TMCL" in problem
    # Answering No lifts the one-time limits.
    account_service.update_account(db, acc.id, AccountUpdate(is_one_time_service=False), rm)
    db.refresh(acc)
    assert labels(acc, "non_anchor_entities") == []
