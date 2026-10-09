"""Standard reports (Triam BRD mark-up §20a). Each report returns {title, columns, rows}; rows only cover
the clients and prospects the user may see. Dates are ISO strings; the screen shows them as DD MM YYYY.

Custom reports and favourites (§20b) follow once Triam gives the details.
"""
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, AccountParty, ApprovalRequest, ApprovalStatus, Prospect, User
from app.services import access_control, client_workflow_service as wf

# Dated documents held on the client and its parties: (field, document)
CLIENT_DATES = [
    ("license_expiry_date", "Trade / Commercial Licence"),
    ("regulatory_license_expiry_date", "Regulatory Licence"),
    ("lei_expiry_date", "LEI"),
    ("passport_expiry_date", "Passport"),
    ("uae_visa_expiry", "UAE Visa"),
    ("engagement_letter_valid_until", "Engagement Letter"),
]
PARTY_DATES = [
    ("id_or_license_expiry", "Passport / Licence"),
    ("uae_visa_expiry", "UAE Visa"),
]


def _accounts(db: Session, user: User) -> list[Account]:
    q = db.query(Account)
    clause = access_control.account_visibility_clause(db, user)
    return (q.filter(clause) if clause is not None else q).all()


BUSINESS_TZ = ZoneInfo("Asia/Dubai")  # Triam works on UAE time; stored timestamps are UTC


def _local_date(dt: datetime) -> date:
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(BUSINESS_TZ).date()


def _today() -> date:
    return datetime.now(BUSINESS_TZ).date()


def _iso(d) -> Optional[str]:
    return d.isoformat() if d else None


def _client_ref(a: Account) -> str:
    return a.client_id or a.temp_id


def _dated_documents(db: Session, user: User) -> list[dict]:
    out = []
    for a in _accounts(db, user):
        for field, label in CLIENT_DATES:
            d = getattr(a, field, None)
            if d:
                out.append({"client": a.company_name, "client_id": _client_ref(a), "holder": a.company_name, "document": label, "expiry": d})
        for p in a.parties:
            for field, label in PARTY_DATES:
                d = getattr(p, field, None)
                if d:
                    out.append({"client": a.company_name, "client_id": _client_ref(a), "holder": f"{p.full_name} ({p.party_role})",
                                "document": label, "expiry": d})
    return out


def documents_expiring(db: Session, user: User, days: int = 30) -> dict:
    today = _today()
    rows = [r for r in _dated_documents(db, user) if 0 <= (r["expiry"] - today).days <= days]
    rows.sort(key=lambda r: r["expiry"])
    return {"title": f"Documents expiring in the next {days} days",
            "columns": ["Client", "Client ID", "Held by", "Document", "Expiry", "Days left"],
            "rows": [[r["client"], r["client_id"], r["holder"], r["document"], _iso(r["expiry"]), (r["expiry"] - today).days] for r in rows]}


def documents_expired(db: Session, user: User) -> dict:
    today = _today()
    rows = [r for r in _dated_documents(db, user) if r["expiry"] < today]
    rows.sort(key=lambda r: r["expiry"])
    return {"title": "Documents with expired status",
            "columns": ["Client", "Client ID", "Held by", "Document", "Expired on", "Days overdue"],
            "rows": [[r["client"], r["client_id"], r["holder"], r["document"], _iso(r["expiry"]), (today - r["expiry"]).days] for r in rows]}


def clients_risk(db: Session, user: User) -> dict:
    today = _today()
    accs = sorted(_accounts(db, user), key=lambda a: (a.next_aml_review_date or date.max, a.company_name))
    return {"title": "Clients with their risk levels and AML review dates",
            "columns": ["Client", "Client ID", "Status", "Risk level", "PEP", "CDD completed", "Next AML review", "Review overdue"],
            "rows": [[a.company_name, _client_ref(a), a.profile_status, a.risk_rating or "—", "Yes" if a.is_pep else "No",
                      _iso(a.cdd_completion_date), _iso(a.next_aml_review_date),
                      "Yes" if a.next_aml_review_date and a.next_aml_review_date < today else "No"] for a in accs]}


def _prospects(db: Session, user: User):
    from app.services import prospect_service
    return prospect_service.list_prospects(db, user)


def prospects_assigned(db: Session, user: User, date_from: Optional[date], date_to: Optional[date]) -> dict:
    rows = []
    for p in _prospects(db, user):
        if not p.assigned_at:
            continue
        d = _local_date(p.assigned_at)
        if (date_from and d < date_from) or (date_to and d > date_to):
            continue
        rows.append([p.prospect_uid, p.company_name, p.owner.name if p.owner else "—", p.assigned_by.name if p.assigned_by else "—",
                     _iso(d), p.status, "Yes" if p.converted_account_id else "No"])
    rows.sort(key=lambda r: r[4], reverse=True)
    period = " to ".join(x for x in (_iso(date_from), _iso(date_to)) if x) or "all time"
    return {"title": f"Prospects assigned ({period})",
            "columns": ["Prospect ID", "Company", "Assigned RM", "Assigned by", "Assigned on", "Status", "Client created"], "rows": rows}


def prospects_unassigned(db: Session, user: User) -> dict:
    now = datetime.now(timezone.utc)
    rows = []
    for p in _prospects(db, user):
        if p.owner_id or p.status == "Lost":
            continue
        created = p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=timezone.utc)
        rows.append([p.prospect_uid, p.company_name, p.source or "—", _iso(_local_date(created)), (now - created).days])
    rows.sort(key=lambda r: r[4], reverse=True)
    return {"title": "Unassigned prospects — ageing", "columns": ["Prospect ID", "Company", "Source", "Created", "Days waiting"], "rows": rows}


def rejected_with_rm(db: Session, user: User) -> dict:
    """Clients sent back to the RM by Compliance or the Approver and not yet resubmitted."""
    now = datetime.now(timezone.utc)
    rows = []
    for a in _accounts(db, user):
        if a.profile_status != wf.WIP:
            continue
        last = (db.query(ApprovalRequest).filter(ApprovalRequest.account_id == a.id, ApprovalRequest.request_type == "client_profile")
                .order_by(ApprovalRequest.id.desc()).first())
        if not last or last.status != ApprovalStatus.REJECTED.value or not last.decided_at:
            continue
        decided = last.decided_at if last.decided_at.tzinfo else last.decided_at.replace(tzinfo=timezone.utc)
        rm = db.get(User, a.spoc_id) if a.spoc_id else None
        rows.append([a.company_name, _client_ref(a), rm.name if rm else "—", last.checker.name if last.checker else "—",
                     _iso(_local_date(decided)), last.reason_text or "", (now - decided).days])
    rows.sort(key=lambda r: r[6], reverse=True)
    return {"title": "Cases pending with RM in Rejected status — ageing",
            "columns": ["Client", "Temporary / Client ID", "RM", "Rejected by", "Rejected on", "Reason", "Days pending"], "rows": rows}


REPORTS = {
    "documents-expiring": "Documents expiring in the next 30 days",
    "documents-expired": "Documents with expired status",
    "clients-risk": "Clients with their risk levels and AML review dates",
    "prospects-assigned": "Prospects assigned for a period",
    "prospects-unassigned": "Unassigned prospects — ageing",
    "rejected-with-rm": "Cases pending with RM in Rejected status — ageing",
}


def run(db: Session, user: User, key: str, days: int = 30, date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
    if key == "documents-expiring":
        return documents_expiring(db, user, days)
    if key == "documents-expired":
        return documents_expired(db, user)
    if key == "clients-risk":
        return clients_risk(db, user)
    if key == "prospects-assigned":
        return prospects_assigned(db, user, date_from, date_to)
    if key == "prospects-unassigned":
        return prospects_unassigned(db, user)
    if key == "rejected-with-rm":
        return rejected_with_rm(db, user)
    raise HTTPException(status_code=404, detail="Unknown report")
