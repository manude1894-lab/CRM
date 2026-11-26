"""Triam 26-11-2026: report IDs, each user's favourite reports, and the Administrator's report settings
(rename, hide, the roles that run a report, its default period)."""
import pytest
from fastapi import HTTPException

from app.models import UserRole
from app.services import report_settings_service as rs, standard_reports_service as rpt
from tests.helpers import auth


def test_every_report_has_a_unique_id_and_it_leads_the_title(db, make_user):
    assert set(rs.CODES) == set(rpt.REPORTS) and len(set(rs.CODES.values())) == len(rs.CODES)
    admin = make_user("Ada Admin", role=UserRole.ADMIN)
    rep = rpt.run(db, admin, "clients-risk")
    assert rep["code"] == "KYC-01" and rep["title"].startswith("KYC-01 ")


def test_favourites_are_each_users_own(client, db, make_user):
    rita, otto = make_user("Rita RM"), make_user("Otto RM")
    assert client.put("/api/v1/reports/standard/clients-risk/favourite", json={"on": True}, headers=auth(rita)).status_code == 204
    mine = {r["key"]: r for r in client.get("/api/v1/reports/standard", headers=auth(rita)).json()}
    theirs = {r["key"]: r for r in client.get("/api/v1/reports/standard", headers=auth(otto)).json()}
    assert mine["clients-risk"]["favourite"] and mine["clients-risk"]["code"] == "KYC-01"
    assert not theirs["clients-risk"]["favourite"]
    client.put("/api/v1/reports/standard/clients-risk/favourite", json={"on": False}, headers=auth(rita))
    assert not {r["key"]: r for r in client.get("/api/v1/reports/standard", headers=auth(rita)).json()}["clients-risk"]["favourite"]


def test_admin_renames_hides_and_chooses_roles(client, db, make_user, make_role):
    admin = make_user("Ada Admin", role=UserRole.ADMIN)
    co_role = make_role("MLRO", ["client.approve"])
    co, rm = make_user("Mia MLRO", business_role=co_role), make_user("Rita RM")
    put = lambda key, body: client.put(f"/api/v1/reports/settings/{key}", json=body, headers=auth(admin))  # noqa: E731
    assert put("amendments", {"name": "Static data maintenance", "hidden": False, "role_ids": None}).status_code == 200
    names = {r["key"]: r["title"] for r in client.get("/api/v1/reports/standard", headers=auth(co)).json()}
    assert names["amendments"] == "Static data maintenance"
    # only the MLRO role may run the risk report now
    put("clients-risk", {"hidden": False, "role_ids": [co_role.id]})
    assert "clients-risk" in rpt.available(co, db) and "clients-risk" not in rpt.available(rm, db)
    with pytest.raises(HTTPException) as e:
        rpt.run(db, rm, "clients-risk")
    assert e.value.status_code == 403
    # hidden: gone for everyone but Administrators
    put("prospects-assigned", {"hidden": True})
    assert "prospects-assigned" not in rpt.available(co, db) and "prospects-assigned" in rpt.available(admin, db)
    # only an Administrator changes settings
    assert client.put("/api/v1/reports/settings/clients-risk", json={"hidden": False}, headers=auth(co)).status_code == 403


def test_default_days(client, db, make_user):
    admin = make_user("Ada Admin", role=UserRole.ADMIN)
    r = client.put("/api/v1/reports/settings/documents-expiring", json={"hidden": False, "default_days": 60}, headers=auth(admin))
    assert r.status_code == 200 and r.json()["default_days"] == 60
    assert "60 days" in rpt.run(db, admin, "documents-expiring")["title"]
    assert client.put("/api/v1/reports/settings/clients-risk", json={"hidden": False, "default_days": 60},
                      headers=auth(admin)).status_code == 400  # that report takes no days
