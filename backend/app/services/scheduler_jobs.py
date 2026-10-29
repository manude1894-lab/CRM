"""Daily reminders, run in-process via APScheduler at 07:00 (no Redis/Celery).

  - Next AML review (BRD §8) due in 30 / 7 days or overdue → the client's Anchor RM and Compliance
  - Trade licence expiry (BRD §5) in 30 / 7 days or expired → the client's Anchor RM
  - Other expiring documents → the client's Anchor RM: regulatory licence, LEI, engagement letter, an
    individual client's passport and UAE visa, and each shareholder / director / signatory / joint
    holder's passport (or licence) and UAE visa
  - Raised invoices past their due date become Overdue → the requester and Accounts
  - Prospects sent to an RM with no client created after PROSPECT_FOLLOW_UP_DAYS → the RM and the assignor
  - Submissions waiting with Compliance / the Approver more than APPROVAL_WAITING_DAYS → the checkers

Each job opens its own DB session since it runs outside the FastAPI request lifecycle. Reminders
are deduped per (client, reminder) so the sweep doesn't repeat one that is still unread.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from app.auth.permissions import has_permission
from app.database import SessionLocal
from app.models import Account, AccountParty, ApprovalRequest, ApprovalStatus, Invoice, Notification, Prospect, User
from app.services import access_control, notification_service
from app.utils.dates import dmy

logger = logging.getLogger("ezeetech.scheduler")

REMINDER_DAYS = (30, 7, 0)
# Only clients Triam services: approved or active, not leaving.
SERVICED_STATUSES = ("Approved", "Active")
PROSPECT_FOLLOW_UP_DAYS = 14
APPROVAL_WAITING_DAYS = 3

# Client-level dates reminded to the Anchor RM: (field, what it is).
CLIENT_DOCUMENTS = (
    ("regulatory_license_expiry_date", "Regulatory licence"),
    ("lei_expiry_date", "LEI"),
    ("engagement_letter_valid_until", "Engagement letter"),
    ("passport_expiry_date", "Passport"),
    ("uae_visa_expiry", "UAE visa"),
)


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


def _expiry_text(what: str, due: date, w: int) -> str:
    return f"{what} {'has expired' if w == 0 else f'expires in {w} days'} ({dmy(due)})"


def check_documents_expiring():
    """Other expiring documents of serviced clients, and of their people."""
    db = SessionLocal()
    try:
        today = date.today()
        for acc in db.query(Account).filter(Account.profile_status.in_(SERVICED_STATUSES)).all():
            for field, what in CLIENT_DOCUMENTS:
                due = getattr(acc, field)
                w = _window(due, today) if due else None
                if w is not None:
                    _remind(db, acc, f"{field[:30]}_{w}d", f"{_expiry_text(what, due, w)} for {_label(acc)}.", compliance=False)
            for p in db.query(AccountParty).filter(AccountParty.account_id == acc.id, AccountParty.removed_at.is_(None)).all():
                for due, what in ((p.id_or_license_expiry, "Licence" if p.constitution == "Entity" else "Passport"),
                                  (p.uae_visa_expiry, "UAE visa")):
                    w = _window(due, today) if due else None
                    if w is not None:
                        _remind(db, acc, f"party{p.id}_{'visa' if what == 'UAE visa' else 'id'}_{w}d",
                                f"{_expiry_text(f'{what} of {p.full_name} ({p.party_role})', due, w)} — {_label(acc)}.",
                                compliance=False)
    finally:
        db.close()


def check_invoices_overdue():
    """A raised invoice past its due date becomes Overdue; the requester and Accounts are told once."""
    db = SessionLocal()
    try:
        today = date.today()
        overdue = db.query(Invoice).filter(Invoice.status == "Raised", Invoice.due_date.isnot(None), Invoice.due_date < today).all()
        if not overdue:
            return
        accounts_team = [u for u in db.query(User).filter(User.is_active == True).all() if has_permission(u, "invoice.manage")]  # noqa: E712
        for inv in overdue:
            inv.status = "Overdue"
            db.commit()
            acc = db.get(Account, inv.account_id)
            message = (f"Invoice {inv.invoice_number or inv.id} for {_label(acc) if acc else 'a client'} is overdue "
                       f"(due {dmy(inv.due_date)}, {inv.currency} {inv.amount}).")
            for uid in {inv.requested_by_id, *(u.id for u in accounts_team)} - {None}:
                notification_service.notify_user(db, uid, message, "invoice_overdue", link="/invoices", account_id=inv.account_id)
    finally:
        db.close()


def _already_reminded(db, user_id: int, key: str) -> bool:
    return db.query(Notification.id).filter(Notification.user_id == user_id, Notification.notification_type == key,
                                            Notification.read_at.is_(None)).first() is not None


def check_prospects_waiting():
    """A prospect sent to an RM with no client created after PROSPECT_FOLLOW_UP_DAYS."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=PROSPECT_FOLLOW_UP_DAYS)
        for p in db.query(Prospect).filter(Prospect.owner_id.isnot(None), Prospect.converted_account_id.is_(None),
                                           Prospect.status != "Lost", Prospect.assigned_at.isnot(None),
                                           Prospect.assigned_at < cutoff).all():
            key = f"prospect_waiting_{p.id}"
            message = (f"Prospect {p.prospect_uid} ({p.company_name}) was sent {PROSPECT_FOLLOW_UP_DAYS}+ days ago "
                       "and no client has been created yet.")
            for uid in {p.owner_id, p.assigned_by_id} - {None}:
                if not _already_reminded(db, uid, key):
                    notification_service.notify_user(db, uid, message, key, link="/prospects")
    finally:
        db.close()


def check_approvals_waiting():
    """A new client or amendment waiting with Compliance / the Approver more than APPROVAL_WAITING_DAYS."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=APPROVAL_WAITING_DAYS)
        for req in db.query(ApprovalRequest).filter(ApprovalRequest.status == ApprovalStatus.PENDING.value,
                                                    ApprovalRequest.submitted_at < cutoff).all():
            acc = db.get(Account, req.account_id)
            if acc is None or notification_service.has_unresolved_notification(db, acc.id, "approval_waiting"):
                continue
            final = req.request_type == "client_profile" and req.stage == "Approver"
            flag = "client.final_approve" if final else "client.approve"
            message = f"{_label(acc)} has been waiting for {'final approval' if final else 'Compliance'} for more than {APPROVAL_WAITING_DAYS} days."
            maker = db.get(User, req.maker_id) if req.maker_id else None
            for u in db.query(User).filter(User.is_active == True).all():  # noqa: E712
                if has_permission(u, flag) and not access_control.same_person(maker, u):
                    notification_service.notify_user(db, u.id, message, "approval_waiting", link="/approvals", account_id=acc.id)
    finally:
        db.close()


def run_daily_sweep():
    """Entry point registered with APScheduler — runs all checks in sequence."""
    for job in (check_aml_reviews_due, check_licences_expiring, check_documents_expiring, check_invoices_overdue,
                check_prospects_waiting, check_approvals_waiting):
        try:
            job()
        except Exception:
            logger.exception("Scheduled job %s failed", job.__name__)
