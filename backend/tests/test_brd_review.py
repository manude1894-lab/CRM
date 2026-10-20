"""BRD line-by-line review fixes (BRD)."""
import io
from decimal import Decimal

import pytest
from fastapi import HTTPException, UploadFile

from app.schemas.account_party import AccountPartyCreate
from app.services import account_party_service, document_service
from tests.test_api_p0 import auth, client  # noqa: F401  (fixture)
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)


def test_inquiry_role_is_read_only(client, make_user, make_role):
    """§13 — "Inquiry & Reports": sees everything, changes nothing."""
    inquiry = make_user("Ian Inquiry", business_role=make_role("Inquiry", ["view.all_clients", "read_only"]))
    assert client.get("/api/v1/accounts", headers=auth(inquiry)).status_code == 200
    r = client.post("/api/v1/prospects", json={"company_name": "Should Not Save"}, headers=auth(inquiry))
    assert r.status_code == 403 and "read-only" in r.json()["detail"]
    assert client.post("/api/v1/notifications/read-all", headers=auth(inquiry)).status_code != 403  # personal actions still allowed


def test_documents_can_belong_to_a_party(db, people, seed_master):
    """§14 — passports / EID / visas are filed in the UBO, Director, Signatory or Joint Holder's section."""
    seed_master("document_category", ["PASSPORT"])
    maker = people["maker"]
    acc = complete_client(db, maker)
    jane = acc.parties[0]
    f = UploadFile(file=io.BytesIO(b"%PDF-1.4"), filename="jane-passport.pdf", headers={"content-type": "application/pdf"})
    document_service.create_for_account(db, acc.id, f, "PASSPORT", maker, party_id=jane.id)
    [d] = document_service.client_folder(db, acc.id, maker)["documents"]
    assert d["party_id"] == jane.id and d["party_name"] == "Jane Owner (Shareholder)"
    with pytest.raises(HTTPException):
        f2 = UploadFile(file=io.BytesIO(b"%PDF-1.4"), filename="x.pdf", headers={"content-type": "application/pdf"})
        document_service.create_for_account(db, acc.id, f2, "PASSPORT", maker, party_id=999999)


def test_entity_shareholder_needs_no_nationality(db, people):
    """§5.1 — nationality applies to people; an entity's country is its country of incorporation."""
    maker = people["maker"]
    acc = complete_client(db, maker)
    account_party_service.create_party(db, acc.id, AccountPartyCreate(
        party_role="Director", constitution="Entity", full_name="Corporate Director Ltd",
        country_of_residence="United Arab Emirates", country_of_incorp_or_birth="BVI"), maker)
    with pytest.raises(HTTPException) as e:
        account_party_service.create_party(db, acc.id, AccountPartyCreate(
            party_role="Director", full_name="Sam Person", country_of_residence="India"), maker)
    assert "Nationality" in e.value.detail
