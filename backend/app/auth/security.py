"""Authentication primitives: password hashing + JWT encode/decode."""
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Passwords ─────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ─── JWT ───────────────────────────────────────────────────────────────────
def _create_token(
    subject: str,
    role: str,
    expires_delta: timedelta,
    token_type: str,
    secret_key: str,
) -> str:
    now = ordered_now()
    expire = now + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "iat_ms": int(now.timestamp() * 1000),
        "type": token_type,
    }
    return jwt.encode(payload, secret_key, algorithm=settings.JWT_ALGORITHM)


_last_ms = 0
_clock_lock = threading.Lock()


def ordered_now() -> datetime:
    """The current time, never the same millisecond twice in this server process. Token issue times and sign-out
    times use it, so "issued before the sign-out" is always clear even where the system clock is coarse (on Windows
    it can tick every 15 ms): signing in, out and in again within one tick still kills the old token only."""
    global _last_ms
    with _clock_lock:
        ms = max(int(datetime.now(timezone.utc).timestamp() * 1000), _last_ms + 1)
        _last_ms = ms
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def create_access_token(user_id: int, role: str) -> str:
    return _create_token(
        subject=str(user_id),
        role=role,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
        secret_key=settings.JWT_SECRET_KEY,
    )


def create_refresh_token(user_id: int, role: str) -> str:
    return _create_token(
        subject=str(user_id),
        role=role,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
        secret_key=settings.JWT_REFRESH_SECRET_KEY,
    )


def issued_before_password_change(payload: dict, user) -> bool:
    """A password change (own or admin reset) ends every session that was open before it; so does signing out
    (review 22-11-2026), which ends the login's sessions on the server."""
    issued_ms = payload.get("iat_ms") or int(payload.get("iat", 0)) * 1000
    return issued_ms < max(password_stamp(user), _stamp(getattr(user, "signed_out_at", None)))


def _stamp(moment) -> int:
    if moment is None:
        return 0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp() * 1000)


def password_stamp(user) -> int:
    changed = user.password_changed_at
    if changed is None:
        return 0
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=timezone.utc)
    return int(changed.timestamp() * 1000)


def create_reset_token(user) -> str:
    """A password-reset link token. It carries the password's current stamp, so it works once:
    any password change, including this reset, makes it invalid."""
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user.id), "type": "reset", "pwd": password_stamp(user), "iat": int(now.timestamp()),
               "exp": int((now + timedelta(minutes=settings.PASSWORD_RESET_MINUTES)).timestamp())}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def reset_token_user_id(token: str) -> tuple[int, int]:
    """(user id, password stamp) from a reset token, or ValueError."""
    payload = decode_token(token, kind="reset")
    try:
        return int(payload["sub"]), int(payload["pwd"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Invalid token: {e}")


def decode_token(token: str, kind: str = "access") -> dict:
    """The payload of a valid token of this kind ("access", "refresh" or "reset"), or ValueError."""
    secret = settings.JWT_REFRESH_SECRET_KEY if kind == "refresh" else settings.JWT_SECRET_KEY
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != kind:
            raise JWTError(f"Invalid token type; expected {kind}")
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")
