"""UAT 06-11-2026 (UAT-14): RM privacy holds with the real roles, whatever flags they carry (BRD §13)."""
import pytest
from fastapi import HTTPException

from app.schemas.prospect import ProspectCreate
from app.services import dashboard_service, my_work_service, prospect_service
from app.services.access_control import is_prospect_coordinator, sees_all_prospects
from tests.helpers import auth


@pytest.fixture()
def team(real_user):
    return {"kalyan": real_user("Rel. Manager", "Kalyan"), "aisha": real_user("Rel. Manager", "Aisha"),
            "priya": real_user("Prospecting Coordinator", "Priya")}


def _assigned_to(db, team, rm_key, name="Assigned Ltd"):
    p = prospect_service.create_prospect(db, ProspectCreate(company_name=name), team["priya"])
    return prospect_service.assign_prospect(db, p.id, team[rm_key].id, None, team["priya"])


def test_rm_does_not_see_or_open_another_rms_prospect(db, team):
    p = _assigned_to(db, team, "aisha")
    assert prospect_service.list_prospects(db, team["kalyan"]) == []
    assert [x.id for x in prospect_service.list_prospects(db, team["aisha"])] == [p.id]
    with pytest.raises(HTTPException) as e:
        prospect_service.get_prospect(db, p.id, team["kalyan"])
    assert e.value.status_code == 403


def test_rm_cannot_take_or_redirect_a_prospect(db, team):
    p = _assigned_to(db, team, "aisha")
    with pytest.raises(HTTPException):
        prospect_service.assign_prospect(db, p.id, team["kalyan"].id, None, team["kalyan"])
    pool = prospect_service.create_prospect(db, ProspectCreate(company_name="Pool Ltd"), team["priya"])
    with pytest.raises(HTTPException):
        prospect_service.assign_prospect(db, pool.id, team["aisha"].id, None, team["kalyan"])
    assert prospect_service.assign_prospect(db, pool.id, team["kalyan"].id, None, team["kalyan"]).owner_id == team["kalyan"].id


def test_prospect_created_by_an_rm_is_their_own(db, team):
    assert prospect_service.create_prospect(db, ProspectCreate(company_name="Mine Ltd"), team["kalyan"]).owner_id == team["kalyan"].id


def test_rm_dashboard_names_only_their_own_team(db, team, real_user):
    junior = real_user("Rel. Manager", "Junior", supervisor=team["kalyan"])
    _assigned_to(db, team, "aisha")
    dash = dashboard_service.build_dashboard(db, team["kalyan"])
    assert {r["name"] for r in dash["portfolio_by_rm"]} == {"Kalyan", junior.name}
    assert dash["kpis"]["prospects_open"] == 0


def test_supervisor_sees_their_team_prospects(db, team, real_user):
    boss = real_user("Sales Manager", "Boss")
    junior = real_user("Rel. Manager", "Junior", supervisor=boss)
    p = prospect_service.create_prospect(db, ProspectCreate(company_name="Junior Ltd"), junior)
    assert [x.id for x in prospect_service.list_prospects(db, boss)] == [p.id]
    assert prospect_service.list_prospects(db, team["kalyan"]) == []


@pytest.mark.parametrize("role, coordinator, sees_all", [
    ("Rel. Manager", False, False), ("RO", False, False), ("FO", False, False), ("Risk Officer", False, False),
    ("Sales Manager", False, False), ("Prospecting Coordinator", True, True), ("MLRO", True, True),
    ("Approver", True, True), ("Accountant", True, True), ("Inquiry", False, True),
])
def test_who_coordinates_and_who_sees_all(real_user, role, coordinator, sees_all):
    u = real_user(role)
    assert is_prospect_coordinator(u) is coordinator
    assert sees_all_prospects(u) is sees_all


def test_only_a_coordinator_gets_the_assignment_work_item(db, team):
    prospect_service.create_prospect(db, ProspectCreate(company_name="Pool Ltd"), team["priya"])

    def keys(u):
        return {w["key"] for w in my_work_service.my_work(db, u)}
    assert "prospects_unassigned" in keys(team["priya"]) and "prospects_unassigned" not in keys(team["kalyan"])


def test_prospect_api_applies_the_same_rule(db, team, client):
    p = _assigned_to(db, team, "aisha")
    assert client.get(f"/api/v1/prospects/{p.id}", headers=auth(team["kalyan"])).status_code == 403
    assert client.get("/api/v1/prospects", headers=auth(team["kalyan"])).json() == []
    assert len(client.get("/api/v1/prospects", headers=auth(team["aisha"])).json()) == 1
