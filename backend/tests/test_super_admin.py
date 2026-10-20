"""The Ezee Tech support account (super admin): hidden from other users, changeable only by itself,
and the only account that can delete user logins."""
from app.models import Account, User
from tests.test_api_p0 import auth, client  # noqa: F401  (fixture)


def _support(db, make_user):
    u = make_user("Admin User", role="admin")
    u.is_super_admin = True
    db.commit()
    return u


def test_support_account_is_invisible_to_other_admins(client, db, make_user):
    support = _support(db, make_user)
    triam_admin = make_user("Triam Admin", role="admin")
    ids = {u["id"] for u in client.get("/api/v1/users", headers=auth(triam_admin)).json()}
    assert support.id not in ids and triam_admin.id in ids
    assert client.get(f"/api/v1/users/{support.id}", headers=auth(triam_admin)).status_code == 404
    assert support.id in {u["id"] for u in client.get("/api/v1/users", headers=auth(support)).json()}


def test_other_admins_cannot_change_or_disable_it(client, db, make_user):
    support = _support(db, make_user)
    triam_admin = make_user("Triam Admin", role="admin")
    for body in ({"password": "Hijack-2026-pass"}, {"is_active": False}, {"email": "x@example.com"}):
        assert client.patch(f"/api/v1/users/{support.id}", json=body, headers=auth(triam_admin)).status_code == 404
    assert client.patch(f"/api/v1/users/{support.id}", json={"name": "System Support"}, headers=auth(support)).status_code == 200
    assert client.patch(f"/api/v1/users/{support.id}", json={"is_active": False}, headers=auth(support)).status_code == 400


def test_only_support_account_deletes_users(client, db, make_user, make_account):
    support = _support(db, make_user)
    triam_admin = make_user("Triam Admin", role="admin")
    test_user = make_user("Test Person")
    assert client.delete(f"/api/v1/users/{test_user.id}", headers=auth(triam_admin)).status_code == 403
    rm = make_user("Busy RM")
    make_account(spoc=rm)
    r = client.delete(f"/api/v1/users/{rm.id}", headers=auth(support))
    assert r.status_code == 409 and "Reassign" in r.json()["detail"]
    assert client.delete(f"/api/v1/users/{test_user.id}", headers=auth(support)).status_code == 204
    assert db.get(User, test_user.id) is None
    assert client.delete(f"/api/v1/users/{support.id}", headers=auth(support)).status_code == 400


def test_audit_shows_support_as_system_support(client, db, make_user):
    support = _support(db, make_user)
    triam_admin = make_user("Triam Admin", role="admin")
    client.post("/api/v1/departments", json={"name": "Treasury"}, headers=auth(support))
    names = {e["user_name"] for e in client.get("/api/v1/audit", headers=auth(triam_admin)).json()}
    assert "System support" in names and "Admin User" not in names
