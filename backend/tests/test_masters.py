"""BRD §18 — admin-managed lists drive what clients may store."""
import pytest
from fastapi import HTTPException

from app.schemas.master import MasterItemCreate, MasterItemUpdate
from app.schemas.account import AccountUpdate
from app.services import master_service, account_service, document_service
from app.models import UserRole


def test_values_must_be_active_codes(db, seed_master):
    seed_master("triam_entity", ["TCPL", "TMCL"], inactive=["TMC"])
    master_service.assert_valid(db, "triam_entity", "TCPL", "Anchor")
    master_service.assert_valid(db, "triam_entity", None, "Anchor")
    with pytest.raises(HTTPException) as e:
        master_service.assert_valid(db, "triam_entity", ["TCPL", "TMC"], "Anchor")
    assert "TMC" in e.value.detail


def test_empty_list_is_not_enforced(db):
    master_service.assert_valid(db, "tag", ["Anything"], "Tags")  # no rows seeded -> no error


def test_create_rejects_duplicates_and_code_defaults_to_label(db):
    item = master_service.create_item(db, "service", MasterItemCreate(label="Payroll"))
    assert item.code == "Payroll"
    with pytest.raises(HTTPException):
        master_service.create_item(db, "service", MasterItemCreate(label="Payroll"))


def test_inactive_items_hidden_from_normal_list(db, seed_master):
    seed_master("tag", ["SPV"], inactive=["Old"])
    assert [i.code for i in master_service.list_items(db, "tag")] == ["SPV"]
    assert {i.code for i in master_service.list_items(db, "tag", include_inactive=True)} == {"SPV", "Old"}


def test_unknown_list_is_404(db):
    with pytest.raises(HTTPException) as e:
        master_service.list_items(db, "nope")
    assert e.value.status_code == 404


def test_code_cannot_be_changed(db):
    item = master_service.create_item(db, "tag", MasterItemCreate(label="SPV"))
    updated = master_service.update_item(db, item.id, MasterItemUpdate(label="Special Purpose Vehicle"))
    assert updated.code == "SPV" and updated.label == "Special Purpose Vehicle"


def test_client_update_validates_against_masters_but_keeps_held_legacy_values(db, seed_master, make_user, make_account):
    seed_master("triam_entity", ["TCPL"], inactive=["TMC"])
    seed_master("tag", ["SPV", "DIFC"])
    admin = make_user(role=UserRole.ADMIN)
    acc = make_account(anchor_entity="TMC", tags="SPV")

    # Re-saving the legacy value is fine; it was already on the record.
    account_service.update_account(db, acc.id, AccountUpdate(anchor_entity="TMC"), admin)
    # Adding a valid tag alongside the existing one is fine.
    account_service.update_account(db, acc.id, AccountUpdate(tags="SPV, DIFC"), admin)
    # A new invalid value is rejected.
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, acc.id, AccountUpdate(tags="SPV, Bogus"), admin)
    assert "Bogus" in e.value.detail
    with pytest.raises(HTTPException):
        account_service.update_account(db, acc.id, AccountUpdate(non_anchor_entities=["TMC"]), admin)


def test_document_category_normalisation(db, seed_master):
    seed_master("document_category", ["PASSPORT"])
    assert document_service._normalise_category(db, "PASSPORT") == "PASSPORT"
    assert document_service._normalise_category(db, "CDD") == "CDD"  # built-in, used by internal flows
    assert document_service._normalise_category(db, "Made up") == "Other"
