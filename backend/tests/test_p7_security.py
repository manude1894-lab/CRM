"""P7 — go-live hardening: lockout, password rules, change password, health checks, headers."""
from datetime import datetime, timedelta, timezone

import pytest

from app.auth.security import hash_password, verify_password
from app.models import AuditLog, User, UserRole
from app.services import security_service
from tests.test_api_p0 import auth, client  # noqa: F401  (fixture)

LOGIN = "/api/v1/auth/login"


def make_login_user(db, password="Strong-pass-2026", email="rita@example.com", role=UserRole.RM):
    u = User(name="Rita", email=email, hashed_password=hash_password(password), role=role)
    db.add(u)
    db.commit()
    return u


def test_account_locks_after_repeated_failures_and_admin_reset_unlocks(client, db, make_user):
    u = make_login_user(db)
    for _ in range(5):
        assert client.post(LOGIN, json={"email": u.email, "password": "nope"}).status_code == 401
    r = client.post(LOGIN, json={"email": u.email, "password": "Strong-pass-2026"})
    assert r.status_code == 429 and "Too many failed attempts" in r.json()["detail"]  # even the right password
    admin = make_user("Ada", role=UserRole.ADMIN)
    assert client.patch(f"/api/v1/users/{u.id}", json={"password": "Reset-pass-2026"}, headers=auth(admin)).status_code == 200
    assert client.post(LOGIN, json={"email": u.email, "password": "Reset-pass-2026"}).status_code == 200


def test_lock_expires(client, db):
    u = make_login_user(db)
    u.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post(LOGIN, json={"email": u.email, "password": "Strong-pass-2026"}).status_code == 200


def test_success_resets_the_failure_count(client, db):
    u = make_login_user(db)
    for _ in range(4):
        client.post(LOGIN, json={"email": u.email, "password": "nope"})
    assert client.post(LOGIN, json={"email": u.email, "password": "Strong-pass-2026"}).status_code == 200
    db.refresh(u)
    assert u.failed_login_count == 0


def test_default_password_login_recommends_a_change(client, db):
    make_login_user(db, password="admin123", email="admin@example.com", role=UserRole.ADMIN)
    body = client.post(LOGIN, json={"email": "admin@example.com", "password": "admin123"}).json()
    assert body["password_change_recommended"] is True


@pytest.mark.parametrize("pw,ok", [("short1", False), ("onlyletterspassword", False), ("1234567890", False),
                                   ("admin123", False), ("Better-pass-77", True)])
def test_password_rules(pw, ok):
    assert (security_service.password_problem(pw, "x@example.com") is None) == ok


def test_change_password(client, db):
    u = make_login_user(db, password="admin123", email="admin@example.com", role=UserRole.ADMIN)
    h = auth(u)
    url = "/api/v1/auth/change-password"
    assert client.post(url, json={"current_password": "wrong", "new_password": "Better-pass-77"}, headers=h).status_code == 400
    r = client.post(url, json={"current_password": "admin123", "new_password": "weak"}, headers=h)
    assert r.status_code == 400 and "at least 10" in r.json()["detail"]
    assert client.post(url, json={"current_password": "admin123", "new_password": "Better-pass-77"}, headers=h).status_code == 204
    db.refresh(u)
    assert verify_password("Better-pass-77", u.hashed_password) and u.password_changed_at is not None
    assert db.query(AuditLog).filter(AuditLog.action == "password_change").count() == 1


def test_admin_cannot_set_a_weak_password(client, make_user):
    admin = make_user("Ada", role=UserRole.ADMIN)
    r = client.post("/api/v1/users", json={"name": "New User", "email": "new@example.com", "password": "rm123456", "role": "rm",
                                          "mobile": "+971 50 111 2222"}, headers=auth(admin))
    assert r.status_code == 400
    r = client.post("/api/v1/users", json={"name": "New User", "email": "new@example.com", "password": "Welcome-2026",
                                          "role": "rm", "mobile": "+971 50 111 2222"}, headers=auth(admin))
    assert r.status_code == 201 and r.json()["mobile"] == "+971501112222"  # mobile is kept on create


def test_health_checks_admin_only_and_flag_default_admin_password(client, db, make_user, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "change-me-in-production-use-openssl-rand-hex-32")
    admin = make_login_user(db, password="admin123", email="admin@example.com", role=UserRole.ADMIN)
    rm = make_user("Rita RM")
    assert client.get("/api/v1/system/health-checks", headers=auth(rm)).status_code == 403
    checks = {c["key"]: c for c in client.get("/api/v1/system/health-checks", headers=auth(admin)).json()}
    assert checks["admin_password"]["ok"] is False and "admin@example.com" in checks["admin_password"]["detail"]
    assert checks["jwt_secret"]["ok"] is False and checks["jwt_secret"]["fix"]
    assert checks["approvers"]["ok"] is False


def test_security_headers(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
