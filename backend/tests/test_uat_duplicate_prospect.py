"""UAT 06-11-2026 (UAT-23): an exact duplicate is blocked at the prospect, the real entry point (BRD §3, §4A, §10)."""
import pytest
from fastapi import HTTPException

from app.models import AuditLog, Prospect, ProspectStatus
from app.schemas.prospect import ProspectCreate, ProspectUpdate
from app.services import prospect_service
from tests import flow
from tests.helpers import auth


def _create(db, user, name, **kw):
    return prospect_service.create_prospect(db, ProspectCreate(company_name=name, **kw), user)


@pytest.mark.parametrize("typed", ["Complete Co", "complete co", "  COMPLETE CO  "])
def test_existing_client_name_is_blocked_whatever_the_capitals(db, real_user, typed):
    rm = real_user("Rel. Manager")
    flow.complete_client(db, rm)
    with pytest.raises(HTTPException) as e:
        _create(db, rm, typed)
    assert e.value.status_code == 409 and "Complete Co" in e.value.detail
    assert db.query(Prospect).count() == 0


def test_open_prospect_name_is_blocked_for_another_rm(db, real_user):
    _create(db, real_user("Rel. Manager"), "Same Name Ltd")
    with pytest.raises(HTTPException) as e:
        _create(db, real_user("Rel. Manager", "Other"), "Same Name Ltd")
    assert e.value.status_code == 409


def test_lost_prospect_name_can_be_used_again(db, real_user):
    rm = real_user("Rel. Manager")
    p = _create(db, rm, "Second Try Ltd")
    prospect_service.update_prospect(db, p.id, ProspectUpdate(status=ProspectStatus.LOST, lost_reason="No budget"), rm)
    assert _create(db, rm, "Second Try Ltd").id != p.id


def test_similar_name_is_still_allowed(db, real_user):
    rm = real_user("Rel. Manager")
    _create(db, rm, "Falcon Trading LLC")
    assert _create(db, rm, "Falcon Trading DMCC")


def test_compliance_override_needs_a_reason_and_is_audited(db, real_user):
    rm, mlro = real_user("Rel. Manager"), real_user("MLRO")
    _create(db, rm, "Twin Ltd")
    with pytest.raises(HTTPException) as e:
        _create(db, rm, "Twin Ltd", allow_duplicate=True, duplicate_reason="Separate legal entity")
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        _create(db, mlro, "Twin Ltd", allow_duplicate=True, duplicate_reason="short")
    assert e.value.status_code == 400
    assert _create(db, mlro, "Twin Ltd", allow_duplicate=True, duplicate_reason="Separate legal entity in ADGM")
    assert "Separate legal entity" in db.query(AuditLog).filter(AuditLog.action == "duplicate_override").one().summary


def test_renaming_onto_an_existing_name_is_blocked_but_keeping_it_is_fine(db, real_user):
    rm = real_user("Rel. Manager")
    _create(db, rm, "Taken Ltd")
    p = _create(db, rm, "Free Ltd")
    with pytest.raises(HTTPException):
        prospect_service.update_prospect(db, p.id, ProspectUpdate(company_name="taken ltd"), rm)
    assert prospect_service.update_prospect(db, p.id, ProspectUpdate(company_name="Free Ltd", notes="More"), rm).notes == "More"


def test_api_returns_the_block(db, real_user, client):
    rm = real_user("Rel. Manager")
    flow.complete_client(db, rm)
    r = client.post("/api/v1/prospects", json={"company_name": "complete co"}, headers=auth(rm))
    assert r.status_code == 409 and "already exists" in r.json()["detail"]
