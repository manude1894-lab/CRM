"""Daily reminders, run in-process via APScheduler at 07:00 (no Redis/Celery).

  - Next AML review (BRD §8) due in 30 / 7 days or overdue → the client's Anchor RM and Compliance
  - Trade licence expiry (BRD §5) in 30 / 7 days or expired → the client's Anchor RM

Each job opens its own DB session since it runs outside the FastAPI request lifecycle. Reminders
are deduped per (client, reminder) so the sweep doesn't repeat one that is still unread.
"""
import logging
from datetime import date

from app.database import SessionLocal
from app.models import Account
from app.services import notification_service
from app.utils.dates import dmy

logger = logging.getLogger("ezeetech.scheduler")

REMINDER_DAYS = (30, 7, 0)
# Only clients Triam services: approved or active, not leaving.
SERVICED_STATUSES = ("Approved", "Active")


def _window(due: date, today: date):
    """The reminder this date is in, or None: 30 / 7 days ahead, or 0 once due or past."""
    days = (due - today).days
    if days <= 0:
        return 0
    return days if days in REMINDER_DAYS else None


def _remind(db, acc: Account, key: str, message: str, compliance: bool) -> None:
    if notification_service.has_unresolved_notification(db, acc.id, key):
        return
    link = f"/accounts/{acc.id}"
    if acc.spoc_id:
        notification_service.notify_user(db, acc.spoc_id, message, key, link=link, account_id=acc.id)
    if compliance:
        notification_service.notify_permission(db, "client.approve", message, key, link=link, account_id=acc.id)


def _label(acc: Account) -> str:
    return f"{acc.company_name} ({acc.client_id or acc.account_uid})"


def check_aml_reviews_due():
    db = SessionLocal()
    try:
        today = date.today()
        for acc in db.query(Account).filter(Account.profile_status.in_(SERVICED_STATUSES),
                                            Account.next_aml_review_date.isnot(None)).all():
            w = _window(acc.next_aml_review_date, today)
            if w is None:
                continue
            when = "is overdue" if w == 0 else f"is due in {w} days"
            _remind(db, acc, f"aml_review_due_{w}d",
                    f"Next AML review of {_label(acc)} {when} ({dmy(acc.next_aml_review_date)}).", compliance=True)
    finally:
        db.close()


def check_licences_expiring():
    db = SessionLocal()
    try:
        today = date.today()
        for acc in db.query(Account).filter(Account.profile_status.in_(SERVICED_STATUSES),
                                            Account.license_expiry_date.isnot(None)).all():
            w = _window(acc.license_expiry_date, today)
            if w is None:
                continue
            when = "has expired" if w == 0 else f"expires in {w} days"
            _remind(db, acc, f"licence_expiry_{w}d",
                    f"Trade licence of {_label(acc)} {when} ({dmy(acc.license_expiry_date)}).", compliance=False)
    finally:
        db.close()


def run_daily_sweep():
    """Entry point registered with APScheduler — runs all checks in sequence."""
    for job in (check_aml_reviews_due, check_licences_expiring):
        try:
            job()
        except Exception:
            logger.exception("Scheduled job %s failed", job.__name__)
