"""SMS notifications (BRD §17 "SMS: required, subject to provider/configuration").

The provider is not chosen yet, so this is a small adapter:
- SMS_ENABLED=false (default): nothing is sent; the message is only logged.
- SMS_PROVIDER=http: POST {"to", "from", "text"} as JSON to SMS_API_URL with
  "Authorization: Bearer SMS_API_KEY". Most UAE SMS gateways accept this shape or need a
  one-line mapping here once Triam picks one.
Sending never raises: an SMS failure must not break the action that triggered it.
"""
import json
import logging
import re
import urllib.request

from app.config import settings

logger = logging.getLogger("ezeetech.sms")

_E164 = re.compile(r"^\+\d{8,15}$")


def normalise(number: str | None) -> str | None:
    """'+971 50 123 4567' -> '+971501234567'; None if it isn't a usable international number."""
    if not number:
        return None
    n = re.sub(r"[\s\-()]", "", number)
    if n.startswith("00"):
        n = "+" + n[2:]
    return n if _E164.match(n) else None


def send_sms(to: str | None, text: str) -> bool:
    number = normalise(to)
    if number is None:
        return False
    text = text[:459]  # three SMS segments at most
    if not settings.SMS_ENABLED:
        logger.info("SMS disabled — would send to %s: %s", number, text)
        return False
    try:
        if settings.SMS_PROVIDER == "http":
            body = json.dumps({"to": number, "from": settings.SMS_SENDER_ID, "text": text}).encode()
            req = urllib.request.Request(settings.SMS_API_URL, data=body, method="POST", headers={
                "Content-Type": "application/json", "Authorization": f"Bearer {settings.SMS_API_KEY}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                ok = 200 <= resp.status < 300
            if not ok:
                logger.warning("SMS gateway answered %s for %s", resp.status, number)
            return ok
        logger.info("SMS provider '%s' — logged only: %s: %s", settings.SMS_PROVIDER, number, text)
        return False
    except Exception:
        logger.exception("SMS to %s failed", number)
        return False
