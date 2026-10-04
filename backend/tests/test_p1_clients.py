"""P1 — client capture rules from BRD §3, §5, §6, §10, §11, §19."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models import UserRole, AuditLog, AccountParty
from app.schemas.account import AccountCreate, AccountUpdate
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_service, account_party_service


def create(db, user, **fields):
    data = {"company_name": "Acme Holdings", "industry": "Fintech", "anchor_entity": "TCPL", **fields}
    return account_service.create_account(db, AccountCreate(**data), user)


# ─── §19 Client ID ──────────────────────────────────────────────────────────

def test_client_ids_count_per_entity(db, make_user):
    rm = make_user()
    a = create(db, rm, company_name="A Ltd")
    b = create(db, rm, company_name="B Ltd")
    c = create(db, rm, company_name="C Ltd", anchor_entity="TMCL")
    assert (a.client_id, b.client_id, c.client_id) == ("TCPL/00001", "TCPL/00002", "TMCL/00001")


def test_anchor_entity_required_to_create(db, make_user):
    with pytest.raises(HTTPException) as e:
        create(db, make_user(), anchor_entity=None)
    assert "Anchor Triam Entity" in e.value.detail


def test_client_id_never_changes_when_anchor_changes(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin)
    account_service.update_account(db, acc.id, AccountUpdate(anchor_entity="TAB"), admin)
    assert acc.client_id == "TCPL/00001"


def test_legacy_client_gets_an_id_once_it_has_an_anchor(db, make_user, make_account):
    admin = make_user(role=UserRole.ADMIN)
    acc = make_account(name="Old Co")  # created before Client IDs, no anchor
    assert acc.client_id is None
    account_service.update_account(db, acc.id, AccountUpdate(anchor_entity="TAB"), admin)
    assert acc.client_id == "TAB/00001"
    assert acc.search_name == "Old Co"


# ─── §3 Unique Search Name, lookup and duplicates ───────────────────────────

def test_search_name_prefilled_and_unique(db, make_user):
    rm = make_user()
    a = create(db, rm, company_name="Acme  Holdings")
    assert a.search_name == "Acme Holdings"
    with pytest.raises(HTTPException) as e:
        create(db, rm, company_name="Different Ltd", search_name="acme holdings")  # case-insensitive
    assert "already used" in e.value.detail


def test_duplicate_blocked_for_ordinary_user(db, make_user):
    rm = make_user()
    create(db, rm)
    with pytest.raises(HTTPException) as e:
        create(db, rm, company_name="ACME HOLDINGS")
    assert e.value.status_code == 409
    with pytest.raises(HTTPException) as e:
        create(db, rm, company_name="Acme Holdings", allow_duplicate=True, duplicate_reason="Separate legal entity in ADGM")
    assert e.value.status_code == 403


def test_approver_can_create_duplicate_with_reason(db, make_user, make_role):
    mlro = make_user(business_role=make_role("MLRO", ["client.approve"]))
    first = create(db, mlro)
    with pytest.raises(HTTPException) as e:
        create(db, mlro, allow_duplicate=True, duplicate_reason="short")
    assert "meaningful reason" in e.value.detail
    dup = create(db, mlro, allow_duplicate=True, duplicate_reason="Separate legal entity registered in ADGM")
    assert dup.duplicate_override_reason.startswith("Separate legal entity")
    assert dup.search_name == "Acme Holdings (TCPL)"  # default disambiguated
    assert dup.client_id != first.client_id
    event = db.query(AuditLog).filter(AuditLog.action == "duplicate_override").one()
    assert event.account_id == dup.id
    assert event.changes["existing_client"] == first.client_id


def test_rename_into_an_existing_name_is_blocked(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    create(db, admin, company_name="Alpha Ltd")
    beta = create(db, admin, company_name="Beta Ltd")
    with pytest.raises(HTTPException) as e:
        account_service.update_account(db, beta.id, AccountUpdate(company_name="alpha ltd"), admin)
    assert e.value.status_code == 409


def test_lookup_from_third_letter_on_word_starts(db, make_user):
    owner, stranger = make_user("Owner"), make_user("Stranger")
    create(db, owner, company_name="Golden Trident Accounting", spoc_id=owner.id)
    create(db, owner, company_name="Silver Holdings", spoc_id=owner.id)
    assert account_service.lookup_by_name(db, owner, "go") == []  # under 3 letters
    hits = account_service.lookup_by_name(db, owner, "tri")
    assert [h["company_name"] for h in hits] == ["Golden Trident Accounting"]
    assert account_service.lookup_by_name(db, owner, "ent") == []  # middle of a word doesn't match
    # Another RM still sees that the name exists (duplicate prevention) but can't open it.
    [hit] = account_service.lookup_by_name(db, stranger, "silver")
    assert hit["can_open"] is False and hit["profile_status"] is None


# ─── §5 field formats ───────────────────────────────────────────────────────

@pytest.mark.parametrize("field,value", [
    ("trn_vat_number", "12AB"),
    ("corp_tax_registration_number", "1234567890123456"),  # 16 digits
    ("license_category", "x" * 26),
    ("license_activities", "x" * 251),
    ("license_number", "x" * 31),
    ("individual_email", "not-an-email"),
    ("financial_year_end", "31-12"),
])
def test_field_formats_rejected(field, value):
    with pytest.raises(ValidationError):
        AccountUpdate(**{field: value})


def test_field_formats_accepted():
    u = AccountUpdate(trn_vat_number=" 100200300400500 ", financial_year_end="12-31", individual_email="a.b@example.com")
    assert u.trn_vat_number == "100200300400500"


def test_licensing_authority_must_come_from_master(db, make_user, seed_master):
    seed_master("licensing_authority", ["DMCC", "Other"])
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin)
    account_service.update_account(db, acc.id, AccountUpdate(licensing_authority="DMCC"), admin)
    with pytest.raises(HTTPException):
        account_service.update_account(db, acc.id, AccountUpdate(licensing_authority="Made Up Authority"), admin)


# ─── §11 status last updated ────────────────────────────────────────────────

def test_status_timestamp_moves_only_on_status_change(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin)
    first = acc.status_updated_at
    assert first is not None and acc.status_updated_by_id == admin.id
    account_service.update_account(db, acc.id, AccountUpdate(industry="Banking"), admin)
    assert acc.status_updated_at == first
    account_service.update_account(db, acc.id, AccountUpdate(profile_status="WIP"), admin)
    assert acc.status_updated_at != first


# ─── §6 shareholders ────────────────────────────────────────────────────────

def _sh(**kw):
    base = dict(party_role="Shareholder", full_name="Jane Doe", mobile_country_code="+971",
                mobile_number="501234567", email="jane@example.com", effective_ownership_percent=Decimal("60"))
    base.update(kw)
    return AccountPartyCreate(**base)


def test_shareholder_contact_mandatory(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin)
    with pytest.raises(HTTPException) as e:
        account_party_service.create_party(db, acc.id, _sh(email=None, mobile_number=None), admin)
    assert "Contact Mobile number" in e.value.detail and "Contact Email" in e.value.detail
    with pytest.raises(HTTPException):
        account_party_service.create_party(db, acc.id, _sh(email="bad"), admin)
    # Directors don't need contact details (optional in BRD §7).
    account_party_service.create_party(db, acc.id, AccountPartyCreate(party_role="Director", full_name="D"), admin)


def test_shareholding_cannot_exceed_100(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin)
    first = account_party_service.create_party(db, acc.id, _sh(), admin)
    account_party_service.create_party(db, acc.id, _sh(full_name="B", effective_ownership_percent=Decimal("40")), admin)
    with pytest.raises(HTTPException) as e:
        account_party_service.create_party(db, acc.id, _sh(full_name="C", effective_ownership_percent=Decimal("0.01")), admin)
    assert "can't exceed 100%" in e.value.detail
    with pytest.raises(HTTPException):
        account_party_service.update_party(db, first.id, AccountPartyUpdate(effective_ownership_percent=Decimal("61")), admin)
    db.refresh(first)
    assert first.effective_ownership_percent == Decimal("60")  # rejected edit was rolled back
    with pytest.raises(HTTPException):
        account_party_service.create_party(db, acc.id, _sh(full_name="D", effective_ownership_percent=Decimal("1.005")), admin)


# ─── Mandatory checklist (enforced at Submit in P2) ─────────────────────────

def test_missing_mandatory_for_a_new_corporate(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin)
    labels = {m["label"] for m in account_service.missing_mandatory(acc)}
    assert {"Anchor RM", "Licensing Authority", "Financial Year End", "At least one Shareholder / UBO",
            "KYC Verification performed by", "CDD/AML Risk Level"} <= labels
    assert "Anchor Triam Entity" not in labels


def test_formation_clients_skip_incorporation_fields(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin, services_obtained=["Company Formation"])
    labels = {m["label"] for m in account_service.missing_mandatory(acc)}
    assert "Incorporation Date" not in labels and "Licensing Authority" not in labels


def test_conditional_fields(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin, is_regulated=True, regulator_name="Other", has_introducer=True,
                 aml_classification="EDD", licensing_authority="Other")
    labels = {m["label"] for m in account_service.missing_mandatory(acc)}
    assert {"Other Regulator details", "License Category", "Introducer Name", "Reason for EDD",
            "Licensing Authority (Other) details"} <= labels


def test_individual_checklist(db, make_user):
    admin = make_user(role=UserRole.ADMIN)
    acc = create(db, admin, account_type="Individual", company_name="John Smith", industry=None)
    labels = {m["label"] for m in account_service.missing_mandatory(acc)}
    assert {"Date of Birth", "Passport Expiry Date", "Nationality"} <= labels
    assert "Licensing Authority" not in labels and "At least one Shareholder / UBO" not in labels
