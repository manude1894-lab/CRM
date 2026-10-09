"""Triam BRD mark-up §4A — every new client starts as a prospect, assigned to an RM."""
import pytest
from fastapi import HTTPException

from app.models import AuditLog, Notification, UserRole
from app.schemas.account import AccountCreate
from app.schemas.prospect import ProspectCreate
from app.services import account_service, prospect_service
from tests.test_api_p0 import auth, client  # noqa: F401  (fixture)


@pytest.fixture()
def team(make_user, make_role):
    return {
        "coordinator": make_user("Pia Coordinator", business_role=make_role("Prospecting Coordinator", ["prospect.assign"])),
        "rm": make_user("Rita RM"),
        "rm2": make_user("Otto RM"),
    }


def test_rm_prospect_is_self_assigned_and_coordinator_may_leave_it_unassigned(db, team):
    mine = prospect_service.create_prospect(db, ProspectCreate(company_name="Mine Ltd"), team["rm"])
    assert mine.owner_id == team["rm"].id and mine.assigned_at is not None
    pool = prospect_service.create_prospect(db, ProspectCreate(company_name="Pool Ltd"), team["coordinator"])
    assert pool.owner_id is None and pool.assigned_at is None
    # RMs see the unassigned pool so they can take a prospect themselves
    assert {p.company_name for p in prospect_service.list_prospects(db, team["rm2"])} == {"Pool Ltd"}


def test_rm_can_take_an_unassigned_prospect_but_not_someone_elses(db, team):
    p = prospect_service.create_prospect(db, ProspectCreate(company_name="Pool Ltd"), team["coordinator"])
    prospect_service.assign_prospect(db, p.id, team["rm"].id, None, team["rm"])
    assert p.owner_id == team["rm"].id and p.assigned_by_id == team["rm"].id
    with pytest.raises(HTTPException) as e:
        prospect_service.assign_prospect(db, p.id, team["rm2"].id, None, team["rm2"])
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as e:
        prospect_service.assign_prospect(db, p.id, team["rm2"].id, None, team["rm"])  # can't hand it to someone else
    assert "Coordinator" in e.value.detail


def test_coordinator_assigns_with_optional_comments(db, team):
    p = prospect_service.create_prospect(db, ProspectCreate(company_name="Pool Ltd"), team["coordinator"])
    with pytest.raises(HTTPException) as e:
        prospect_service.assign_prospect(db, p.id, team["rm"].id, "word " * 251, team["coordinator"])
    assert "250 words" in e.value.detail
    prospect_service.assign_prospect(db, p.id, team["rm"].id, "Discussed with the Unit Manager; DIFC formation lead", team["coordinator"])
    assert p.owner_id == team["rm"].id and p.assignor_comments.startswith("Discussed")
    note = db.query(Notification).filter(Notification.user_id == team["rm"].id).one()
    assert "Pool Ltd" in note.message and "Unit Manager" in note.message
    assert db.query(AuditLog).filter(AuditLog.subject_type == "Prospect", AuditLog.action == "assign").count() == 1


def test_client_is_created_from_an_assigned_prospect(db, team):
    rm = team["rm"]
    pool = prospect_service.create_prospect(db, ProspectCreate(company_name="Pool Ltd"), team["coordinator"])
    with pytest.raises(HTTPException) as e:
        account_service.create_account(db, AccountCreate(company_name="Pool Ltd", anchor_entity="TCPL", prospect_id=pool.id), rm)
    assert "Assign prospect" in e.value.detail
    prospect_service.assign_prospect(db, pool.id, rm.id, None, team["coordinator"])
    acc = account_service.create_account(db, AccountCreate(company_name="Pool Ltd", anchor_entity="TCPL", prospect_id=pool.id), rm)
    assert acc.prospect_id == pool.id and acc.temp_id == pool.prospect_uid and acc.client_id is None
    assert acc.spoc_id == rm.id  # the prospect's RM becomes the Anchor RM
    assert pool.converted_account_id == acc.id and pool.status == "Won"
    with pytest.raises(HTTPException) as e:
        account_service.create_account(db, AccountCreate(company_name="Pool Two Ltd", anchor_entity="TCPL", prospect_id=pool.id), rm)
    assert "already been created" in e.value.detail


def test_api_requires_a_prospect_for_new_clients(client, make_user):
    rm, admin = make_user("Rita RM"), make_user("Ada Admin", role=UserRole.ADMIN)
    body = {"company_name": "Direct Ltd", "anchor_entity": "TCPL"}
    r = client.post("/api/v1/accounts", json=body, headers=auth(rm))
    assert r.status_code == 400 and "prospect" in r.json()["detail"]
    assert client.post("/api/v1/accounts", json=body, headers=auth(admin)).status_code == 201
