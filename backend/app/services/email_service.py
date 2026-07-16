"""Thin wrapper around fastapi-mail for notification emails.

Controlled by settings.SMTP_ENABLED so demo/dev environments without real
SMTP credentials never block or crash on a send attempt.
"""
import logging

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

from app.config import settings

logger = logging.getLogger("ezeetech.email")

_fm: FastMail | None = None


def _get_mailer() -> FastMail:
    global _fm
    if _fm is None:
        conf = ConnectionConfig(
            MAIL_USERNAME=settings.SMTP_USERNAME,
            MAIL_PASSWORD=settings.SMTP_PASSWORD,
            MAIL_FROM=settings.SMTP_FROM_EMAIL,
            MAIL_FROM_NAME=settings.SMTP_FROM_NAME,
            MAIL_PORT=settings.SMTP_PORT,
            MAIL_SERVER=settings.SMTP_HOST,
            MAIL_STARTTLS=settings.SMTP_USE_TLS,
            MAIL_SSL_TLS=not settings.SMTP_USE_TLS,
            USE_CREDENTIALS=bool(settings.SMTP_USERNAME),
        )
        _fm = FastMail(conf)
    return _fm


async def send_notification_email(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_ENABLED:
        logger.info("SMTP disabled — would send to %s: %s", to_email, subject)
        return
    try:
        message = MessageSchema(
            subject=subject,
            recipients=[to_email],
            body=body,
            subtype=MessageType.plain,
        )
        await _get_mailer().send_message(message)
    except Exception:
        logger.exception("Failed to send notification email to %s", to_email)
