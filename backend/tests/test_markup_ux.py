"""Triam BRD mark-up §2 / §13 — last login, role-level "My work", company email domain."""
import pytest
from fastapi import HTTPException

from app.auth.security import hash_password
from app.config import settings
from app.models import UserRole
from app.schemas.user import UserCreate
from app.services import my_work_service, user_service
from tests import flow
from tests.test_api_p0 import client  # noqa: F401  (fixture)
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)


def test_last_login_is_shown_at_the_next_login(client, db, make_user):
    u = make_user("Rita RM")
    u.hashed_password = hash_password("Rita-Pass-2026")
    db.commit()
    first = client.post("/api/v1/auth/login", json={"email": u.email, "password": "Rita-Pass-2026"}).json()["user"]
    assert first["previous_login_at"] is None and first["last_login_at"] is not None
    second = client.post("/api/v1/auth/login", json={"email": u.email, "password": "Rita-Pass-2026"}).json()["user"]
    assert second["previous_login_at"] == first["last_login_at"]


def _counts(db, user):
    return {i["key"]: i["count"] for i in my_work_service.my_work(db, user)}


def test_my_work_follows_the_role(db, people):
    maker, checker, approver = people["maker"], people["checker"], people["approver"]
    acc = complete_client(db, maker)
    assert _counts(db, maker)["my_in_progress"] == 1
    flow.submit(db, acc, maker)
    assert _counts(db, checker)["compliance_new"] == 1 and "approver" not in _counts(db, checker)
    assert _counts(db, approver)["approver"] == 0
    flow.compliance_approve(db, acc, checker)
    assert _counts(db, checker)["compliance_new"] == 0 and _counts(db, approver)["approver"] == 1
    assert _counts(db, maker)["my_with_review"] == 1


def test_company_email_domain_when_configured(db, monkeypatch):
    monkeypatch.setattr(settings, "USER_EMAIL_DOMAINS", "asktriam.com")
    with pytest.raises(HTTPException) as e:
        user_service.create_user(db, UserCreate(name="Out Side", email="someone@gmail.com", password="Strong-Pass-2026", role=UserRole.RM))
    assert "@asktriam.com" in e.value.detail
    user_service.create_user(db, UserCreate(name="In Side", email="rita@asktriam.com", password="Strong-Pass-2026", role=UserRole.RM))
