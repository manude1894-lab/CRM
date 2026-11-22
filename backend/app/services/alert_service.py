"""Error alerts (review 22-11-2026, package 6): a crash on the server or in someone's browser is logged with a short
reference and sent to the support desk, so problems are known before a user reports them.

Where alerts go is set on the hosting platform: ALERT_EMAILS (comma-separated, uses the CRM's SMTP mailbox) and/or
ALERT_WEBHOOK_URL (a Teams or Slack incoming webhook). The same error is sent at most once in 15 minutes, and at
most 30 alerts an hour, so a fault that repeats on every request cannot flood the desk. Alerts carry the page or
route, the error type and message and the version; no client data is added to them.
"""
import asyncio
import json
import logging
import secrets
import threading
import time
import urllib.request
from collections import deque
from typing import Optional

from app.config import settings

logger = logging.getLogger("ezeetech.alerts")

REPEAT_SECONDS = 15 * 60
MAX_PER_HOUR = 30
_lock = threading.Lock()
_last_sent: dict[str, float] = {}
_sent_times: deque = deque()
recent: deque = deque(maxlen=50)  # the latest errors, for System Health


def new_reference() -> str:
    return secrets.token_hex(3).upper()


def _recipients() -> list[str]:
    return [e.strip() for e in (settings.ALERT_EMAILS or "").split(",") if e.strip()]


def configured() -> bool:
    return bool(_recipients() or settings.ALERT_WEBHOOK_URL)


def _should_send(key: str, now: float) -> bool:
    with _lock:
        while _sent_times and now - _sent_times[0] > 3600:
            _sent_times.popleft()
        if now - _last_sent.get(key, -1e9) < REPEAT_SECONDS or len(_sent_times) >= MAX_PER_HOUR:
            return False
        _last_sent[key] = now
        _sent_times.append(now)
        return True


def _deliver(subject: str, body: str) -> None:
    if settings.ALERT_WEBHOOK_URL:
        try:
            req = urllib.request.Request(settings.ALERT_WEBHOOK_URL, data=json.dumps({"text": f"{subject}\n{body}"}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=10).close()
        except Exception:
            logger.exception("Alert webhook failed")
    if _recipients():
        from app.services.email_service import send_notification_email
        for to in _recipients():
            try:
                asyncio.run(send_notification_email(to, subject, body))
            except Exception:
                logger.exception("Alert email failed")


def _send_in_background(subject: str, body: str) -> None:
    threading.Thread(target=_deliver, args=(subject, body), daemon=True).start()


def report(source: str, where: str, error_type: str, message: str, reference: Optional[str] = None,
           extra: Optional[str] = None) -> str:
    """Logs an error and alerts the desk. `source` is "server" or "browser". Returns the reference."""
    from app.services.security_service import running_commit
    reference = reference or new_reference()
    message = (message or "")[:500]
    logger.error("[%s] %s error at %s: %s: %s", reference, source, where, error_type, message)
    recent.append({"at": time.time(), "reference": reference, "source": source, "where": where[:200],
                   "error": f"{error_type}: {message}"[:300]})
    if not configured() or not _should_send(f"{source}|{where}|{error_type}", time.monotonic()):
        return reference
    subject = f"[{settings.APP_NAME}] {source} error {reference}: {error_type}"
    body = "\n".join(line for line in (
        f"Reference: {reference}", f"Where: {where}", f"Error: {error_type}: {message}",
        f"Version: {running_commit() or 'unknown'}", f"Environment: {settings.APP_URL or 'not set'}",
        extra and f"\n{extra[:2000]}") if line)
    _send_in_background(subject, body)
    return reference


def reset() -> None:
    with _lock:
        _last_sent.clear()
        _sent_times.clear()
        recent.clear()
