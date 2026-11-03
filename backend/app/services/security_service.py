"""P7 hardening: password rules, login lockout and the go-live system health check."""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.permissions import has_permission
from app.auth.security import create_reset_token, hash_password, password_stamp, reset_token_user_id, verify_password
from app.config import settings
from app.models import Notification, User, UserRole
from app.services import notification_service

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


def set_password(user: User, new_password: str) -> None:
    """Check the rules and store a new password. Every session opened before it ends, and any lock clears."""
    assert_password_ok(new_password, user.email)
    user.hashed_password = hash_password(new_password)
    password_set(user)


# ─── Forgotten password ─────────────────────────────────────────────────────

RESET_REQUEST_GAP_SECONDS = 120
_last_reset_request: dict[int, float] = {}


def reset_emails_enabled() -> bool:
    return bool(settings.SMTP_ENABLED and settings.APP_URL)


def request_password_reset(db: Session, email: str) -> None:
    """Email a one-time reset link (when email is set up) and tell the administrators, who can also reset
    it from Admin → Users. Runs after the response is sent, so the answer is the same and as fast for any
    email; at most one request per account every two minutes is acted on."""
    from app.services.user_service import find_by_email  # user_service imports this module
    user = find_by_email(db, email)
    if not user or not user.is_active:
        return
    now = time.monotonic()
    if now - _last_reset_request.get(user.id, -RESET_REQUEST_GAP_SECONDS) < RESET_REQUEST_GAP_SECONDS:
        return
    _last_reset_request[user.id] = now
    if reset_emails_enabled():
        link = f"{settings.APP_URL.rstrip('/')}/reset-password?token={create_reset_token(user)}"
        notification_service.send_email_best_effort(
            user.email, "TRIAM: reset your password",
            f"Hello {user.name},\n\nUse this link to choose a new password. It works once and expires in "
            f"{settings.PASSWORD_RESET_MINUTES} minutes:\n\n{link}\n\nIf you did not ask for this, ignore this email.")
    if user.is_super_admin:
        return  # the support account is never shown to Triam's administrators
    log_event(db, "password_reset_request", f"{user.name} asked for a password reset", user_id=user.id,
              subject_type="User", subject_id=user.id)
    db.commit()
    message = f"{user.name} ({user.email}) asked for a password reset"
    for admin in db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True,  # noqa: E712
                                       User.is_super_admin == False, User.id != user.id).all():  # noqa: E712
        already = db.query(Notification).filter(Notification.user_id == admin.id, Notification.message == message,
                                                Notification.read_at.is_(None)).first()
        if not already:
            notification_service.notify_user(db, admin.id, message, "password_reset_request")


def reset_password(db: Session, token: str, new_password: str) -> None:
    expired = HTTPException(status_code=400, detail="This reset link has expired or was already used. Ask for a new one.")
    try:
        user_id, stamp = reset_token_user_id(token)
    except ValueError:
        raise expired
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user or stamp != password_stamp(user):
        raise expired
    set_password(user, new_password)
    if not user.is_super_admin:
        log_event(db, "password_reset", f"{user.name} reset their password", user_id=user.id, subject_type="User", subject_id=user.id)
    db.commit()


# ─── Go-live health check (Admin → System Health) ───────────────────────────

def _check(key, label, ok, fix, severity="high", detail=None):
    return {"key": key, "label": label, "ok": bool(ok), "severity": severity, "fix": None if ok else fix, "detail": detail}


def system_health(db: Session) -> list[dict]:
    users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
    admins = [u for u in users if u.role == UserRole.ADMIN]
    default_admins = [("the support account" if u.is_super_admin else u.email)
                      for u in admins if verify_password("admin123", u.hashed_password)]
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
        _check("app_url", "Password reset emails can link to the CRM", bool(settings.APP_URL),
               "Set APP_URL to the CRM's web address on the hosting platform (e.g. https://crm.asktriam.com).",
               severity="medium"),
        _check("sms", "SMS notifications switched on", settings.SMS_ENABLED,
               "Waiting for Triam's choice of SMS provider (SMS_ENABLED, SMS_PROVIDER, SMS_API_URL, SMS_API_KEY).", severity="low"),
        _check("backups", "Daily database backups confirmed", False,
               "Cannot be checked from inside the application. Confirm daily backups on the hosting platform, with weekly "
               "copies kept, and test one restore.",
               severity="medium"),
    ]
