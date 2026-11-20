"""Triam 20-11-2026 (S T Krishna): the onboarding form begins with the Triam entities, then the RMs. The entities decide
the services a corporate client may take; a service left over after the entity was changed is refused at Submit."""
from app.models import MasterItem
from app.schemas.account import AccountUpdate
from app.services import account_service
from tests import flow


def _services(db):
    for code, entities in (("Audit Services", ["TCPL"]), ("Offshore Company Formation Services", ["TBVI"]),
                           ("Accounting & Bookkeeping", [])):
        db.add(MasterItem(list_type="service", code=code, label=code, sort_order=0, is_active=True, meta={"entities": entities}))
    db.commit()


def labels(acc):
    return [m["label"] for m in account_service.missing_mandatory(acc)]


def test_a_service_the_entities_do_not_offer_is_refused(db, people):
    _services(db)
    rm = people["maker"]
    acc = flow.complete_client(db, rm)  # TCPL, "Accounting & Bookkeeping" (offered by every entity)
    assert labels(acc) == []
    account_service.update_account(db, acc.id, AccountUpdate(
        nature_of_services_sought=["Accounting & Bookkeeping", "Offshore Company Formation Services"]), rm)
    db.refresh(acc)
    assert labels(acc) == ["'Offshore Company Formation Services' is not offered by TCPL. Remove it, or add the Triam entity that offers it"]
    account_service.update_account(db, acc.id, AccountUpdate(non_anchor_entities=["TBVI"]), rm)  # add the entity that offers it
    db.refresh(acc)
    assert labels(acc) == []


def test_changing_the_entity_flags_the_services_left_behind(db, people):
    _services(db)
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    account_service.update_account(db, acc.id, AccountUpdate(nature_of_services_sought=["Audit Services"]), rm)
    account_service.update_account(db, acc.id, AccountUpdate(anchor_entity="TBVI"), rm)
    db.refresh(acc)
    assert any("'Audit Services' is not offered by TBVI" in m for m in labels(acc))


def test_individual_clients_are_not_limited_by_entity(db, people):
    _services(db)
    rm = people["maker"]
    acc = flow.complete_client(db, rm)
    acc.account_type = "Individual"
    acc.nature_of_services_sought = ["Offshore Company Formation Services"]
    db.commit()
    assert account_service.entity_service_problems(db, acc) == []
