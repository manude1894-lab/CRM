"""Triam 02-11-2026: master lists in alphabetical order; countries with code, risk and change history."""
from app.models import AuditLog, CountryRisk, UserRole
from app.services import master_service
from tests.helpers import auth


def test_services_are_listed_alphabetically_with_other_last(db, seed_master):
    seed_master("service", ["VAT Services", "Other", "Audit Services", "Company Formation"])
    seed_master("service_request_status", ["Received", "In Progress", "Completed"])
    assert [i.label for i in master_service.list_items(db, "service")] == ["Audit Services", "Company Formation", "VAT Services", "Other"]
    # lists whose order means something keep the administrator's order
    assert [i.label for i in master_service.list_items(db, "service_request_status")] == ["Received", "In Progress", "Completed"]


def test_admin_changes_country_code_and_risk_with_history(client, db, make_user):
    admin, rm = make_user(role=UserRole.ADMIN), make_user()
    c = CountryRisk(name="Atlantis", risk_level="Low", score=1)
    db.add(c)
    db.commit()
    assert client.patch(f"/api/v1/countries/{c.id}", json={"risk_level": "High"}, headers=auth(rm)).status_code == 403
    r = client.patch(f"/api/v1/countries/{c.id}", json={"code": "at", "risk_level": "High"}, headers=auth(admin))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "AT" and body["risk_level"] == "High" and body["changed_at"]
    assert client.patch(f"/api/v1/countries/{c.id}", json={"risk_level": "Severe"}, headers=auth(admin)).status_code == 422
    [entry] = db.query(AuditLog).filter(AuditLog.subject_type == "Country", AuditLog.subject_id == c.id).all()
    assert "risk level Low → High" in entry.summary
    db.refresh(c)
    assert c.score == 5


def test_compliance_sees_high_risk_countries_linked_to_the_client(client, db, make_user, make_account, make_role):
    from app.models import AccountParty
    db.add_all([CountryRisk(name="Atlantis", risk_level="High", score=5), CountryRisk(name="Lemuria", risk_level="Low", score=1)])
    rm = make_user("Rita")
    mlro = make_user("Mia", business_role=make_role("MLRO", ["client.approve", "view.all_clients"]))
    acc = make_account(name="Sea Co", spoc=rm, country="Lemuria", operating_address={"city": "X", "country": "atlantis"})
    db.add(AccountParty(account_id=acc.id, party_role="Shareholder", full_name="Ned", nationality="Atlantis", country_of_residence="Lemuria"))
    db.commit()
    url = f"/api/v1/accounts/{acc.id}/country-risk"
    assert client.get(url, headers=auth(rm)).status_code == 403  # Compliance's view, not the RM's
    cdd_only = make_user("Carl", business_role=make_role("CDD desk", ["client.cdd_edit", "view.all_clients"]))
    assert client.get(url, headers=auth(cdd_only)).status_code == 200  # whoever fills in the CDD section sees it
    r = client.get(url, headers=auth(mlro))
    assert r.status_code == 200, r.text
    assert r.json() == [{"country": "Atlantis", "who": "Sea Co", "field": "Operating address"},
                        {"country": "Atlantis", "who": "Shareholder: Ned", "field": "Nationality"}]
