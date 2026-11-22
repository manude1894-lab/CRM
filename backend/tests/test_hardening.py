"""Review 22-11-2026, package 2 (hardening): sign-in limit per network address, reset-request limit, server-side
sign-out, upload content checks, the running commit in the health check, and 15-minute access tokens."""
import io

import pytest
from fastapi import HTTPException, UploadFile

from app.auth.security import hash_password
from app.config import settings
from app.models import User, UserRole
from app.services import document_service, rate_limit

LOGIN = "/api/v1/auth/login"


def _user(db, email="rita@example.com", password="Strong-pass-2026"):
    u = User(name="Rita", email=email, hashed_password=hash_password(password), role=UserRole.RM)
    db.add(u)
    db.commit()
    return u


def _login(client, email, password, ip="203.0.113.7"):
    return client.post(LOGIN, json={"email": email, "password": password}, headers={"X-Forwarded-For": ip})


def test_one_address_is_held_back_after_many_failures_across_accounts(client, db):
    _user(db, "real@example.com")
    for i in range(rate_limit.login_failures.max_events):  # one wrong password on each of many accounts
        assert _login(client, f"guess{i}@example.com", "wrong-pass-1").status_code == 401
    r = _login(client, "real@example.com", "Strong-pass-2026")
    assert r.status_code == 429 and "15 minutes" in r.json()["detail"]  # even the right password, from that address
    assert _login(client, "real@example.com", "Strong-pass-2026", ip="198.51.100.9").status_code == 200  # others are fine


def test_the_address_is_the_one_the_proxy_added(client, db):
    _user(db, "real@example.com")
    for i in range(rate_limit.login_failures.max_events):
        _login(client, f"guess{i}@example.com", "wrong-pass-1", ip="1.2.3.4, 203.0.113.7")  # left part is made up
    assert _login(client, "real@example.com", "Strong-pass-2026", ip="9.9.9.9, 203.0.113.7").status_code == 429


def test_reset_requests_are_limited_per_address(client, db):
    for _ in range(rate_limit.reset_requests.max_events):
        assert client.post("/api/v1/auth/forgot-password", json={"email": "x@example.com"},
                           headers={"X-Forwarded-For": "203.0.113.8"}).status_code == 200
    r = client.post("/api/v1/auth/forgot-password", json={"email": "x@example.com"}, headers={"X-Forwarded-For": "203.0.113.8"})
    assert r.status_code == 429


def test_signing_out_ends_the_session_on_the_server(client, db):
    _user(db)
    tokens = _login(client, "rita@example.com", "Strong-pass-2026").json()
    auth = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth).status_code == 204
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 401  # the copied token is dead
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    again = _login(client, "rita@example.com", "Strong-pass-2026").json()  # signing in again works
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {again['access_token']}"}).status_code == 200


def test_access_tokens_last_15_minutes():
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15


def _file(name, data, ctype):
    return UploadFile(file=io.BytesIO(data), filename=name, headers={"content-type": ctype})


@pytest.mark.parametrize("name, data, ctype", [
    ("passport.pdf", b"MZ\x90\x00 a program, renamed", "application/pdf"),
    ("photo.png", b"%PDF-1.4 not an image", "image/png"),
    ("form.docx", b"plain text", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
])
def test_a_renamed_file_is_refused(name, data, ctype):
    with pytest.raises(HTTPException) as e:
        document_service.read_upload(_file(name, data, ctype))
    assert e.value.status_code == 400 and "not a real" in e.value.detail


@pytest.mark.parametrize("name, data, ctype", [
    ("passport.pdf", b"%PDF-1.7\n...", "application/pdf"),
    ("scan.pdf", b"\r\n%PDF-1.4 with a few bytes first", "application/pdf"),
    ("photo.png", bytes.fromhex("89504e470d0a1a0a") + b"...", "image/png"),
    ("photo.jpg", bytes.fromhex("ffd8ffe0") + b"...", "image/jpeg"),
    ("form.docx", bytes.fromhex("504b0304") + b"...", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("old.xls", bytes.fromhex("d0cf11e0a1b11ae1") + b"...", "application/vnd.ms-excel"),
])
def test_real_files_pass(name, data, ctype):
    assert document_service.read_upload(_file(name, data, ctype))[0] == name


def test_health_reports_the_running_commit(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abcdef1234567890")
    assert client.get("/health").json() == {"status": "ok", "commit": "abcdef1"}
