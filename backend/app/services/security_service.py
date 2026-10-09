"""P7 hardening: password rules, login lockout and the go-live system health check."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.permissions import has_permission
from app.auth.security import verify_password
from app.config import settings
from app.models import User, UserRole

# Passwords shipped with the demo / minimal seed. Anyone still using one is told to change it.
DEFAULT_PASSWORDS = {"admin123", "rm123", "ops123", "screen123"}
_DEFAULT_SECRETS = {"change-me-in-production-use-openssl-rand-hex-32", "change-me-refresh-secret-in-production"}


def password_problem(password: str, email: str | None = None) -> str | None:
    """Rules for any new password: at least 10 characters with letters and digits, not a known
    default and not the user's own email."""
    if len(password or "") < 10:
        return "must be at least 10 characters"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "must contain both letters and numbers"
    if password.lower() in DEFAULT_PASSWORDS:
        return "is a default password; choose another"
    if email and password.lower() == email.lower():
        return "can't be the same as the email address"
    return None


def assert_password_ok(password: str, email: str | None = None) -> None:
    problem = password_problem(password, email)
    if problem:
        raise HTTPException(status_code=400, detail=f"Password {problem}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes
    return dt


def assert_not_locked(user: User | None) -> None:
    if user is None:
        return
    until = _aware(user.locked_until)
    if until and until > _now():
        minutes = max(1, int((until - _now()).total_seconds() // 60) + 1)
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}, or ask an administrator to reset your password.")


def record_failure(user: User | None) -> None:
    if user is None:
        return
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= settings.LOGIN_MAX_ATTEMPTS:
        user.locked_until = _now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
        user.failed_login_count = 0


def record_success(user: User) -> None:
    user.failed_login_count = 0
    user.locked_until = None


def password_set(user: User) -> None:
    """Call whenever a new password is stored (also clears any lock)."""
    user.password_changed_at = _now()
    user.failed_login_count = 0
    user.locked_until = None


# ─── Go-live health check (Admin → System Health) ───────────────────────────

def _check(key, label, ok, fix, severity="high", detail=None):
    return {"key": key, "label": label, "ok": bool(ok), "severity": severity, "fix": None if ok else fix, "detail": detail}


def system_health(db: Session) -> list[dict]:
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    admins = [u for u in users if u.role == UserRole.ADMIN]
    default_admins = [u.email for u in admins if verify_password("admin123", u.hashed_password)]
    approvers = [u for u in users if has_permission(u, "client.approve") and u.role != UserRole.ADMIN]
    cors = settings.CORS_ALLOW_ALL
    return [
        _check("admin_password", "Administrator passwords changed from the default", not default_admins,
               "Sign in as each administrator and use Change password (bottom of the menu).",
               detail=", ".join(default_admins) or None),
        _check("jwt_secret", "Login token signing keys are private", settings.JWT_SECRET_KEY not in _DEFAULT_SECRETS
               and settings.JWT_REFRESH_SECRET_KEY not in _DEFAULT_SECRETS,
               "On the hosting platform set JWT_SECRET_KEY and JWT_REFRESH_SECRET_KEY to two different long random values "
               "(e.g. the output of `openssl rand -hex 32`). Everyone will need to sign in again."),
        _check("cors", "Only the CRM's own web address may call the API", not cors,
               "Set CORS_ALLOW_ALL=false and CORS_ORIGINS to the CRM's web address on the hosting platform."),
        _check("approvers", "At least two Compliance approvers", len(approvers) >= 2,
               "Give the CO / MLRO / Dy MLRO business roles to at least two active users, so an approver's own "
               "submissions can be reviewed by someone else.", detail=f"{len(approvers)} active approver(s)"),
        _check("smtp", "Email notifications switched on", settings.SMTP_ENABLED,
               "Set SMTP_ENABLED=true with the Triam mailbox settings (SMTP_HOST, SMTP_PORT, SMTP_USERNAME, "
               "SMTP_PASSWORD, SMTP_FROM_EMAIL).", severity="medium"),
        _check("sms", "SMS notifications switched on", settings.SMS_ENABLED,
               "Waiting for Triam's choice of SMS provider (SMS_ENABLED, SMS_PROVIDER, SMS_API_URL, SMS_API_KEY).", severity="low"),
        _check("backups", "Daily database backups confirmed", False,
               "Cannot be checked from inside the application. Confirm daily backups on the hosting platform, with weekly "
               "copies kept (BRD discussion: daily backups, weekend data retained), and test one restore. See docs/go-live-checklist.md.",
               severity="medium"),
    ]
