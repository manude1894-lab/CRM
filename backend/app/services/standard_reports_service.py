"""Standard reports (BRD §20a; Triam UAT 18-11-2026 rows 92-147). Each report returns {title, columns, rows};
rows only cover the clients and prospects the user may see, so the same report is department-wise for a
Sales Manager / supervisor, the RM's own for an RM, and everything for Compliance and Admin. Dates are ISO
strings; the screen shows them as DD MM YYYY.

Custom reports and favourites (§20b) follow once Triam gives the details.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Account, ApprovalRequest, ApprovalStatus, User
from app.services import access_control, client_workflow_service as wf

# Dated documents held on the client and its parties: (expiry field, document type, number field or None)
CLIENT_DATES = [
    ("license_expiry_date", "Trade / Commercial Licence", "license_number"),
    ("regulatory_license_expiry_date", "Regulatory Licence", None),
    ("lei_expiry_date", "LEI", "lei_number"),
    ("passport_expiry_date", "Passport", "passport_number"),
    ("uae_visa_expiry", "UAE Visa", "uae_visa_number"),
    ("engagement_letter_valid_until", "Engagement Letter", None),
]
PARTY_DATES = [
    ("id_or_license_expiry", "Passport / Licence", "passport_number"),
    ("uae_visa_expiry", "UAE Visa", "uae_visa_number"),
]
# Approved and serviced: they carry a risk level and AML review dates.
SERVICED = (wf.APPROVED, wf.ACTIVE, wf.INACTIVE, wf.MARKED_EXIT)


def _accounts(db: Session, user: User) -> list[Account]:
    """The clients the user may see, with their people and prospect loaded in bulk (two queries in all, not one
    per client: review 22-11-2026, package 4)."""
    from sqlalchemy.orm import selectinload
    q = db.query(Account).options(selectinload(Account.parties), selectinload(Account.prospect))
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


def _pros_id(a: Account) -> str:
    """The Prospect ID the client came from (its temporary ID), or the internal number for imported clients."""
    return a.temp_id


class _Names:
    """Look-ups read once per report: user names, the Anchor RM's department, and Client Tag labels
    (Triam UAT 19-11-2026 adds Client Tag and Department to the reports)."""
    def __init__(self, db: Session):
        self.db, self._users, self._depts, self._tags = db, {}, None, None

    def _user(self, user_id):
        if user_id not in self._users:
            self._users[user_id] = self.db.get(User, user_id)
        return self._users[user_id]

    def __call__(self, user_id: Optional[int]) -> str:
        u = self._user(user_id) if user_id else None
        return u.name if u else "—"

    def dept(self, user_id: Optional[int]) -> str:
        """The department of the given user (the client's Anchor RM)."""
        from app.models import Department
        if self._depts is None:
            self._depts = {d.id: d.name for d in self.db.query(Department).all()}
        u = self._user(user_id) if user_id else None
        return self._depts.get(u.department_id, "—") if u and u.department_id else "—"

    def tags(self, a: Account) -> str:
        """The client's tags, by their labels in the Tag master list."""
        from app.services import master_service
        if self._tags is None:
            self._tags = {i.code: i.label for i in master_service.list_items(self.db, "tag", include_inactive=True)}
        codes = [t.strip() for t in (a.tags or "").split(",") if t.strip()]
        return ", ".join(self._tags.get(c, c) for c in codes) or "—"


# ─── Documents (3.1, 3.2) ───────────────────────────────────────────────────

def _dated_documents(db: Session, user: User) -> list[dict]:
    out = []
    for a in _accounts(db, user):
        if a.profile_status in CLOSED_STATUSES:
            continue
        for field, label, number in CLIENT_DATES:
            d = getattr(a, field, None)
            if d:
                out.append({"acc": a, "holder": a.company_name, "document": label,
                            "number": getattr(a, number, None) if number else None, "expiry": d})
        # Triam UAT 25-11-2026: one person with several roles (e.g. Shareholder and Authorised Signatory) holds one
        # passport and one visa: list each document once, with all the person's roles.
        from app.services.account_service import group_people
        for records in group_people(a.parties):
            roles = ", ".join(dict.fromkeys(r.party_role for r in records))
            seen = set()
            for p in records:
                for field, label, number in PARTY_DATES:
                    d = getattr(p, field, None)
                    num = getattr(p, number, None) if number else None
                    key = (label, (num or "").strip().upper(), d)
                    if d and key not in seen:
                        seen.add(key)
                        out.append({"acc": a, "holder": f"{records[0].full_name} ({roles})", "document": label,
                                    "number": num, "expiry": d})
    return out


DOCUMENT_COLUMNS = ["Anchor Triam Entity", "Client ID", "Anchor RM", "Client Name", "Client Tag", "Held by", "Doc Type", "Doc No.",
                    "Doc Expiry Date"]


def _document_row(r: dict, names: _Names) -> list:
    a = r["acc"]
    return [a.anchor_entity or "—", _client_ref(a), names(a.spoc_id), a.company_name, names.tags(a), r["holder"], r["document"],
            r["number"] or "—", _iso(r["expiry"])]


def documents_expiring(db: Session, user: User, days: int = 30) -> dict:
    today, names = _today(), _Names(db)
    rows = [r for r in _dated_documents(db, user) if 0 <= (r["expiry"] - today).days <= days]
    rows.sort(key=lambda r: r["expiry"])
    return {"title": f"Documents expiring in the next {days} days", "columns": [*DOCUMENT_COLUMNS, "Days left"],
            "rows": [[*_document_row(r, names), (r["expiry"] - today).days] for r in rows]}


def documents_expired(db: Session, user: User) -> dict:
    today, names = _today(), _Names(db)
    rows = [r for r in _dated_documents(db, user) if r["expiry"] < today]
    rows.sort(key=lambda r: r["expiry"])
    return {"title": "Documents with expired status", "columns": [*DOCUMENT_COLUMNS, "Days overdue"],
            "rows": [[*_document_row(r, names), (today - r["expiry"]).days] for r in rows]}


# ─── Risk and AML reviews (3.3, 3.4, 3.5) ───────────────────────────────────

def _serviced(db: Session, user: User) -> list[Account]:
    return [a for a in _accounts(db, user) if a.profile_status in SERVICED]


def clients_risk(db: Session, user: User) -> dict:
    today, names = _today(), _Names(db)
    accs = sorted(_serviced(db, user), key=lambda a: (a.next_aml_review_date or date.max, a.company_name))
    return {"title": "Clients with their risk levels and AML review dates",
            "columns": ["Anchor Triam Entity", "Client ID", "Client Name", "Client Tag", "Anchor RM", "Risk Level", "Last Review Date",
                        "Next Review Date", "Days overdue"],
            "rows": [[a.anchor_entity or "—", _client_ref(a), a.company_name, names.tags(a), names(a.spoc_id), a.risk_rating or "—",
                      _iso(a.cdd_completion_date), _iso(a.next_aml_review_date),
                      max((today - a.next_aml_review_date).days, 0) if a.next_aml_review_date else "—"] for a in accs]}


SHORT_NUMBER = 3  # an incorporation or licence number shorter than this is almost certainly a typing slip


def data_issues(a: Account, today: date) -> list[str]:
    """Triam data review 21-11-2026: what is wrong or missing on a client past onboarding. Records entered before
    a rule existed, or loaded through the import, can break rules that the form now enforces."""
    issues = []
    company = a.account_type != "Individual"
    forming = a.client_category == "Under Formation"
    if a.profile_status in SERVICED:
        if not a.client_id:
            issues.append("No Client ID")
        if not a.risk_rating:
            issues.append("No risk level")
    if a.license_start_date and a.license_start_date > today:
        issues.append(f"Licence start date in the future ({_iso(a.license_start_date)})")
    if a.incorporation_date and a.incorporation_date > today:
        issues.append(f"Incorporation date in the future ({_iso(a.incorporation_date)})")
    if a.license_start_date and a.incorporation_date and a.license_start_date < a.incorporation_date:
        issues.append("Licence start date before the incorporation date")
    if company and not forming:
        for value, label in ((a.registration_number, "Incorporation number"), (a.license_number, "Licence number")):
            if value and len(value.strip()) < SHORT_NUMBER:
                issues.append(f"{label} looks too short ('{value.strip()}')")
        if a.is_regulated is None:
            issues.append("Regulated (Yes / No) not answered")
        if not a.licensing_authority:
            issues.append("No registering authority")
    if a.engagement_letter_signed is None:
        issues.append("Engagement letter signed (Yes / No) not answered")
    if a.is_pep and a.risk_rating and a.risk_rating != "High":
        issues.append(f"PEP with {a.risk_rating} risk")
    if (a.edd_reason or "").strip() and a.risk_rating != "High":
        issues.append(f"EDD reason recorded but risk is {a.risk_rating or 'not set'}")
    return issues


def data_quality(db: Session, user: User) -> dict:
    """Clients submitted for approval or beyond with data to correct; drafts are left out (they are still being
    filled in, and Submit checks them)."""
    today, names = _today(), _Names(db)
    rows = []
    for a in sorted(_accounts(db, user), key=lambda a: a.company_name.lower()):
        if a.profile_status not in (*SERVICED, wf.AWAITING):
            continue
        issues = data_issues(a, today)
        if issues:
            rows.append([a.company_name, _client_ref(a), a.anchor_entity or "—", names(a.spoc_id), a.profile_status,
                         len(issues), "; ".join(issues)])
    return {"title": "Client data to correct",
            "columns": ["Client Name", "Client ID", "Anchor Triam Entity", "Anchor RM", "Status", "Issues", "What to correct"],
            "rows": rows}


def aml_reviews_due(db: Session, user: User, days: int = 30) -> dict:
    today, names = _today(), _Names(db)
    accs = sorted((a for a in _serviced(db, user)
                   if a.next_aml_review_date and 0 <= (a.next_aml_review_date - today).days <= days),
                  key=lambda a: a.next_aml_review_date)
    return {"title": f"AML reviews due in the next {days} days",
            "columns": ["Anchor Triam Entity", "Client ID", "Anchor RM", "Client Name", "Client Tag", "AML Expiry Date", "Days left"],
            "rows": [[a.anchor_entity or "—", _client_ref(a), names(a.spoc_id), a.company_name, names.tags(a), _iso(a.next_aml_review_date),
                      (a.next_aml_review_date - today).days] for a in accs]}


def aml_reviews_expired(db: Session, user: User) -> dict:
    today, names = _today(), _Names(db)
    accs = sorted((a for a in _serviced(db, user) if a.next_aml_review_date and a.next_aml_review_date < today),
                  key=lambda a: a.next_aml_review_date)
    return {"title": "AML review expired",
            "columns": ["Anchor Triam Entity", "Client ID", "Anchor RM", "Client Name", "Client Tag", "AML Expiry Date", "Days overdue"],
            "rows": [[a.anchor_entity or "—", _client_ref(a), names(a.spoc_id), a.company_name, names.tags(a), _iso(a.next_aml_review_date),
                      (today - a.next_aml_review_date).days] for a in accs]}


# ─── Prospects (3.6) ────────────────────────────────────────────────────────

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
        if p.owner_id or p.status == "Dropped":
            continue
        created = p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=timezone.utc)
        # Department and Client Tag (Triam UAT 19-11-2026): a prospect holds neither yet, and has no RM to take them from.
        rows.append([p.prospect_uid, _iso(_local_date(created)), p.company_name, p.contact_name or "—", "—", "—",
                     p.contact_email or "—", p.contact_phone or "—", p.source or "—", (now - created).days])
    rows.sort(key=lambda r: r[9], reverse=True)
    return {"title": "Unassigned prospects (ageing)",
            "columns": ["Prospect ID", "Logged Date", "Prospect Name", "Contact Name", "Department", "Client Tag", "Contact Email",
                        "Contact Phone No.", "Source", "Days waiting"],
            "rows": rows}


# ─── Rejected (3.7) ─────────────────────────────────────────────────────────

def rejected_with_rm(db: Session, user: User) -> dict:
    """Clients sent back to the RM by Compliance or the Approver and not yet resubmitted."""
    from app.services import master_service
    now, names = datetime.now(timezone.utc), _Names(db)
    labels = {i.code: i.label for i in master_service.list_items(db, "rejection_reason", include_inactive=True)}
    rows = []
    for a in _accounts(db, user):
        if a.profile_status != wf.REJECTED:
            continue
        last = (db.query(ApprovalRequest).filter(ApprovalRequest.account_id == a.id, ApprovalRequest.request_type == "client_profile")
                .order_by(ApprovalRequest.id.desc()).first())
        if not last or last.status != ApprovalStatus.REJECTED.value or not last.decided_at:
            continue
        decided = last.decided_at if last.decided_at.tzinfo else last.decided_at.replace(tzinfo=timezone.utc)
        reason = ". ".join(x for x in (labels.get(last.reason_code, last.reason_code), last.reason_text) if x)
        rows.append([a.anchor_entity or "—", _pros_id(a), a.company_name, names.dept(a.spoc_id), names.tags(a), names(a.spoc_id),
                     names(last.checker_id), _iso(_local_date(decided)), reason, (now - decided).days])
    rows.sort(key=lambda r: r[9], reverse=True)
    return {"title": "Clients in Rejected status (ageing)",
            "columns": ["Anchor Triam Entity", "Pros ID", "Client Name", "Department", "Client Tag", "Anchor RM", "Rejected by",
                        "Rejected on", "Reason for Rejection", "Ageing (days)"],
            "rows": rows}


# ─── Under formation (row 93, 3.8) ──────────────────────────────────────────

# Details an Under Formation client may leave blank at onboarding (BRD §5, Triam UAT 05-11-2026).
FORMATION_DETAILS = (
    ("registration_number", "Incorporation Certificate No."),
    ("incorporation_date", "Incorporation Date"),
    ("license_number", "Licence No."),
    ("license_start_date", "Licence Start Date"),
    ("license_expiry_date", "Licence Expiry Date"),
    ("registered_address", "Registered Address"),
    ("operating_address", "Operating Address"),
    ("financial_year_end", "Financial Year End"),
)
UNDER_FORMATION_DAYS = 30
CLOSED_STATUSES = ("Exited", "Dropped")


def formation_details_missing(a: Account) -> list[str]:
    out = []
    for field, label in FORMATION_DETAILS:
        v = getattr(a, field, None)
        if field.endswith("_address"):
            v = (v or {}).get("line1")
        if not (v.strip() if isinstance(v, str) else v):
            out.append(label)
    return out


def under_formation(db: Session, user: User, days: int = UNDER_FORMATION_DAYS) -> dict:
    """Triam UAT 10-11-2026 (row 24) and 18-11-2026 (rows 93, 147): approved clients still Under Formation, so
    the RM follows up the licence and incorporation details. Ageing counts from the Final approval; the user
    picks the period (only clients pending that many days or more are listed; 0 lists all)."""
    today, names = _today(), _Names(db)
    rows = []
    for a in _accounts(db, user):
        if a.client_category != "Under Formation" or a.profile_status not in SERVICED or not a.approved_at:
            continue
        approved = _local_date(a.approved_at)
        ageing = (today - approved).days
        if ageing < days:
            continue
        rows.append([a.anchor_entity or "—", _client_ref(a), a.company_name, names.dept(a.spoc_id), names.tags(a), names(a.spoc_id),
                     a.profile_status, _iso(approved), ", ".join(formation_details_missing(a)) or "None", ageing])
    rows.sort(key=lambda r: r[9], reverse=True)
    return {"title": f"Clients under formation, pending {days} days or more after approval" if days else "Clients under formation",
            "columns": ["Anchor Triam Entity", "Client ID", "Client Name", "Department", "Client Tag", "Anchor RM", "Status",
                        "Approved on", "Missing Details", "Ageing from approval (days)"],
            "rows": rows}


# ─── Client onboarding status (row 104-121) ─────────────────────────────────

ONBOARDING_COLUMNS = ["Anchor Triam Entity", "Pros ID", "Anchor RM", "Source", "Assigned Date", "Client Name", "Regn Authority",
                      "Regulator", "Services applied", "Status"]
# Statuses for the "other than approved" report's filter, as Triam listed them.
ONBOARDING_STATUSES = (wf.NEW, wf.WIP, wf.PENDING_CLIENT, wf.PENDING_AUTHORITY, wf.REJECTED, wf.AWAITING, wf.DROPPED, wf.ON_HOLD)


def _onboarding_row(a: Account, names: _Names) -> list:
    p = a.prospect
    authority = a.licensing_authority_other if a.licensing_authority == "Other" else a.licensing_authority
    regulator = (a.regulator_other if a.regulator_name == "Other" else a.regulator_name) if a.is_regulated else "Not regulated"
    status = a.profile_status
    if status == wf.AWAITING and a.approval_stage:
        status = f"{status} ({'Final approval' if a.approval_stage == wf.STAGE_APPROVER else 'Compliance'})"
    return [a.anchor_entity or "—", _pros_id(a), names(a.spoc_id), (p.source if p else None) or "—",
            _iso(_local_date(p.assigned_at)) if p and p.assigned_at else "—", a.company_name, authority or "—",
            regulator or "—", "; ".join(a.nature_of_services_sought or []) or "—", status]


def _in_department(db: Session, a: Account, department_id: Optional[int]) -> bool:
    if not department_id:
        return True
    rm = db.get(User, a.spoc_id) if a.spoc_id else None
    return bool(rm and rm.department_id == department_id)


def _period(date_from: Optional[date], date_to: Optional[date]) -> str:
    return " to ".join(x for x in (_iso(date_from), _iso(date_to)) if x) or "all time"


def onboarding_approved(db: Session, user: User, date_from: Optional[date] = None, date_to: Optional[date] = None,
                        department_id: Optional[int] = None) -> dict:
    """Clients given the Final approval in the period, latest first."""
    names, picked = _Names(db), []
    for a in _accounts(db, user):
        if not a.approved_at or not _in_department(db, a, department_id):
            continue
        d = _local_date(a.approved_at)
        if (date_from and d < date_from) or (date_to and d > date_to):
            continue
        picked.append((d, a))
    picked.sort(key=lambda x: (x[0], x[1].id), reverse=True)
    return {"title": f"Client onboarding: approved ({_period(date_from, date_to)})", "columns": [*ONBOARDING_COLUMNS, "Approved on"],
            "rows": [[*_onboarding_row(a, names), _iso(d)] for d, a in picked]}


def onboarding_in_progress(db: Session, user: User, date_from: Optional[date] = None, date_to: Optional[date] = None,
                           status: Optional[str] = None, department_id: Optional[int] = None) -> dict:
    """Clients not yet approved, by when they were created (assigned to the RM), latest first. Filter by status."""
    if status and status not in ONBOARDING_STATUSES:
        raise HTTPException(status_code=400, detail=f"Status must be one of {', '.join(ONBOARDING_STATUSES)}")
    names, picked = _Names(db), []
    for a in _accounts(db, user):
        if a.profile_status not in ONBOARDING_STATUSES or (status and a.profile_status != status) \
                or not _in_department(db, a, department_id):
            continue
        d = _local_date(a.created_at) if a.created_at else None
        if d and ((date_from and d < date_from) or (date_to and d > date_to)):
            continue
        picked.append((d, a))
    picked.sort(key=lambda x: (x[0] or date.min, x[1].id), reverse=True)
    title = f"Client onboarding: {status or 'not yet approved'} ({_period(date_from, date_to)})"
    return {"title": title, "columns": [*ONBOARDING_COLUMNS, "Created on", "Status note"],
            "rows": [[*_onboarding_row(a, names), _iso(d),
                      " · ".join(x for x in (a.status_reason_code, a.status_reason) if x) or "—"] for d, a in picked]}


# ─── Triam UAT 19-11-2026: amendments, invoices and service requests (rows 155-176) ─────────────────────

class Filters:
    """The filters Triam asked for on the new reports: Triam Anchor Entity, Department, Client Tag, Anchor RM."""
    def __init__(self, entity: Optional[str] = None, department_id: Optional[int] = None, tag: Optional[str] = None,
                 rm_id: Optional[int] = None, account_id: Optional[int] = None):
        self.entity, self.department_id, self.tag, self.rm_id = entity or None, department_id or None, tag or None, rm_id or None
        self.account_id = account_id or None  # Triam UAT 25-11-2026: one client (the call / visit reports)

    def passes(self, db: Session, a: Account) -> bool:
        if self.account_id and a.id != self.account_id:
            return False
        if self.entity and a.anchor_entity != self.entity:
            return False
        if self.rm_id and a.spoc_id != self.rm_id:
            return False
        if self.tag and self.tag not in [t.strip() for t in (a.tags or "").split(",")]:
            return False
        return _in_department(db, a, self.department_id)


def _within(d: Optional[date], date_from: Optional[date], date_to: Optional[date]) -> bool:
    return d is not None and not ((date_from and d < date_from) or (date_to and d > date_to))


def _authority(a: Account) -> str:
    return (a.licensing_authority_other if a.licensing_authority == "Other" else a.licensing_authority) or "—"


def _blank(v) -> str:
    return "—" if v in (None, "") else str(v)


# ── Calls and visits (Triam UAT 25-11-2026 rows 190 and 194) ──────────────────────

def _period(date_from, date_to) -> str:
    """A report's period in words, dates as DD MM YYYY like the rest of the CRM."""
    shown = [d.strftime("%d %m %Y") for d in (date_from, date_to) if d]
    return " to ".join(shown) or "all time"


VISIT_COLUMNS = ["Date of Report", "Call / Visit", "Client ID", "Client Name", "Client Tag", "RM Name"]
NOT_DONE_DAYS = 90  # the period looked at when no dates are given


def _final_reports(db: Session, user: User, accounts: dict) -> list:
    from app.models import Activity, ActivityStatus
    return (db.query(Activity).filter(Activity.account_id.in_(list(accounts) or [-1]), Activity.status == ActivityStatus.COMPLETED)
            .order_by(Activity.activity_date.desc(), Activity.id.desc()).all())


def visits_recorded(db: Session, user: User, date_from=None, date_to=None, f: "Filters" = None) -> dict:
    """Row 190: the calls and visits recorded (saved as final) in the period; latest first."""
    f, names = f or Filters(), _Names(db)
    accounts = {a.id: a for a in _accounts(db, user) if f.passes(db, a)}
    rows = [[_iso(r.activity_date), "Visit" if r.activity_type.value == "Visit Report" else "Call", _client_ref(accounts[r.account_id]),
             accounts[r.account_id].company_name, names.tags(accounts[r.account_id]), names(r.owner_id)]
            for r in _final_reports(db, user, accounts) if _within(r.activity_date, date_from, date_to)]
    return {"title": f"Calls / visits recorded ({_period(date_from, date_to)})", "columns": VISIT_COLUMNS, "rows": rows}


def visits_not_done(db: Session, user: User, date_from=None, date_to=None, f: "Filters" = None) -> dict:
    """Row 194: clients Triam services with no call or visit recorded in the period (the last 90 days when no dates
    are given), with their last call / visit, if any; the longest without one first."""
    f, names, today = f or Filters(), _Names(db), _today()
    date_from = date_from or (today - timedelta(days=NOT_DONE_DAYS) if not date_to else None)
    date_to = date_to or today
    accounts = {a.id: a for a in _accounts(db, user) if a.profile_status in SERVICED and f.passes(db, a)}
    last, seen_in_period = {}, set()
    for r in _final_reports(db, user, accounts):
        last.setdefault(r.account_id, r)
        if _within(r.activity_date, date_from, date_to):
            seen_in_period.add(r.account_id)
    rows = []
    for a in sorted(accounts.values(), key=lambda a: (last[a.id].activity_date if a.id in last else date.min, a.company_name.lower())):
        if a.id in seen_in_period:
            continue
        r = last.get(a.id)
        rows.append([_iso(r.activity_date) if r else None,
                     ("Visit" if r.activity_type.value == "Visit Report" else "Call") if r else "None yet",
                     _client_ref(a), a.company_name, names.tags(a), names(a.spoc_id)])
    return {"title": f"Clients with no call / visit ({_period(date_from, date_to)})",
            "columns": ["Last Report", "Last Call / Visit", "Client ID", "Client Name", "Client Tag", "RM Name"], "rows": rows}


def amendments_report(db: Session, user: User, date_from=None, date_to=None, f: "Filters" = None) -> dict:
    """Clients Static Data Amendments (row 156): every approved amendment, one line per field changed, with the
    value before and after. Dated by the approval; latest first."""
    from app.services import amendment_service
    f, names = f or Filters(), _Names(db)
    visible = {a.id: a for a in _accounts(db, user) if f.passes(db, a)}
    reqs = (db.query(ApprovalRequest).filter(ApprovalRequest.request_type == amendment_service.TYPE,
                                             ApprovalRequest.status == ApprovalStatus.APPROVED.value,
                                             ApprovalRequest.account_id.in_(list(visible) or [-1]))
            .order_by(ApprovalRequest.decided_at.desc(), ApprovalRequest.id.desc()).all())
    rows = []
    for r in reqs:
        approved = _local_date(r.decided_at) if r.decided_at else None
        if (date_from or date_to) and not _within(approved, date_from, date_to):
            continue
        a = visible[r.account_id]
        head = [a.anchor_entity or "—", _client_ref(a), names.tags(a), a.company_name, names(a.spoc_id),
                _iso(_local_date(r.submitted_at)) if r.submitted_at else None, names(r.maker_id), names(r.checker_id), _iso(approved)]
        changes = r.changes or {}
        lines = [("Client", c.get("label") or c.get("field"), c.get("old"), c.get("new")) for c in changes.get("account", [])]
        for p in changes.get("parties", []):
            who = f"{p.get('name') or '—'} ({p.get('role') or '—'})"
            action = p.get("action")
            if action == "removed":
                lines.append((who, "Person removed", None, None))
            elif action == "added" and not p.get("changes"):
                lines.append((who, "Person added", None, None))
            for c in p.get("changes", []):
                lines.append((who + (", added" if action == "added" else ""), c.get("label") or c.get("field"), c.get("old"), c.get("new")))
        for where, field, old, new in lines or [("—", "—", None, None)]:
            rows.append([*head, where, field, _blank(old), _blank(new)])
    return {"title": f"Clients static data amendments ({_period(date_from, date_to)})",
            "columns": ["Anchor Triam Entity", "Client ID", "Client Tag", "Client Name", "Anchor RM", "Amendment done on", "Amended by",
                        "Approved by", "Approved on", "Record", "Field", "Previous", "New"],
            "rows": rows}


def _invoices(db: Session, user: User, f: "Filters", kind: Optional[str] = None):
    from app.models import Invoice
    visible = {a.id: a for a in _accounts(db, user) if f.passes(db, a)}
    q = db.query(Invoice).filter(Invoice.account_id.in_(list(visible) or [-1]), Invoice.requested_at.isnot(None),
                                 Invoice.status != "Cancelled")
    if kind:
        q = q.filter(Invoice.kind == kind)
    return [(inv, visible[inv.account_id]) for inv in q.order_by(Invoice.requested_at.desc(), Invoice.id.desc()).all()]


INVOICE_COLUMNS = ["Date Request raised", "PROS ID", "Client ID", "Client Name", "Client Tag", "Regn Authority", "CUR", "AMOUNT",
                   "Invoice Raised on", "Invoice No.", "Status"]


def _invoice_row(inv, a: Account, names: _Names) -> list:
    return [_iso(_local_date(inv.requested_at)), _pros_id(a), a.client_id or "—", a.company_name, names.tags(a), _authority(a),
            inv.currency, float(inv.amount or 0), _iso(inv.raised_date), inv.invoice_number or "—", inv.status]


def invoices_report(db: Session, user: User, kind: str, date_from=None, date_to=None, f: "Filters" = None) -> dict:
    """Onboarding Services / Service Request Invoice reports (rows 162, 166): requests sent to Accounts in the
    period, by the date the request was raised; latest first."""
    f, names = f or Filters(), _Names(db)
    rows = [_invoice_row(inv, a, names) for inv, a in _invoices(db, user, f, kind)
            if not (date_from or date_to) or _within(_local_date(inv.requested_at), date_from, date_to)]
    title = "Onboarding services invoices" if kind == "Onboarding" else "Service request invoices"
    return {"title": f"{title} ({_period(date_from, date_to)})", "columns": INVOICE_COLUMNS, "rows": rows}


REQUEST_TYPES = ("Onboarding", "Service Request")


def invoices_pending(db: Session, user: User, date_from=None, date_to=None, request_type: Optional[str] = None,
                     f: "Filters" = None) -> dict:
    """Raising Invoices Pending (row 170): requests with Accounts not yet raised as an invoice; longest waiting first."""
    if request_type and request_type not in REQUEST_TYPES:
        raise HTTPException(status_code=400, detail=f"Request Type must be one of {', '.join(REQUEST_TYPES)}")
    f, names, today = f or Filters(), _Names(db), _today()
    rows = []
    for inv, a in _invoices(db, user, f, request_type):
        if inv.status != "Requested":
            continue
        raised_on = _local_date(inv.requested_at)
        if (date_from or date_to) and not _within(raised_on, date_from, date_to):
            continue
        rows.append([_iso(raised_on), inv.kind or "—", _client_ref(a), a.company_name, names.tags(a), _authority(a), inv.currency,
                     float(inv.amount or 0), None, (today - raised_on).days])
    rows.sort(key=lambda r: r[9], reverse=True)
    return {"title": f"Raising invoices pending ({request_type or 'all requests'})",
            "columns": ["Date Request raised", "Request Type", "PROS ID / CLIENT ID", "Client Name", "Client Tag", "Regn Authority",
                        "CUR", "AMOUNT", "Invoice Raised on", "Days pending"],
            "rows": rows}


def service_requests_ageing(db: Session, user: User, date_from=None, date_to=None, sr_type: Optional[str] = None,
                            f: "Filters" = None) -> dict:
    """Service Requests Status, Ageing (row 174): each request with its status and age; latest first. Ageing runs
    from the date the request was raised to its completion, or to today while open."""
    from app.models import Instruction
    from app.services import master_service
    f, names, today = f or Filters(), _Names(db), _today()
    type_labels = {i.code: i.label for i in master_service.list_items(db, "service_request_type", include_inactive=True)}
    visible = {a.id: a for a in _accounts(db, user) if f.passes(db, a)}
    q = db.query(Instruction).filter(Instruction.account_id.in_(list(visible) or [-1]))
    if sr_type:
        q = q.filter(Instruction.instruction_type == sr_type)
    rows = []
    for inst in q.all():
        raised = inst.date_received or (_local_date(inst.created_at) if inst.created_at else None)
        if (date_from or date_to) and not _within(raised, date_from, date_to):
            continue
        a = visible[inst.account_id]
        end = inst.date_completed or today
        kind = (inst.other_description if inst.instruction_type == "Other" and inst.other_description
                else type_labels.get(inst.instruction_type, inst.instruction_type))
        rows.append([_iso(raised), kind, a.anchor_entity or "—", _client_ref(a), a.company_name, names.tags(a), names(a.spoc_id),
                     inst.status, _iso(inst.date_completed), (end - raised).days if raised else "—"])
    rows.sort(key=lambda r: (r[0] or ""), reverse=True)
    return {"title": f"Service requests status and ageing ({_period(date_from, date_to)})",
            "columns": ["Date Request raised", "Request Type", "Anchor Triam Entity", "CLIENT ID", "Client Name", "Client Tag", "Anchor RM",
                        "Status", "Completed on", "Ageing (days)"],
            "rows": rows}


REPORTS = {
    "onboarding-approved": "Client onboarding: approved (date range)",
    "onboarding-in-progress": "Client onboarding: other than approved (date range, status)",
    "under-formation": "Clients under formation",
    "documents-expiring": "Documents expiring in the next N days",
    "documents-expired": "Documents with expired status",
    "clients-risk": "Clients with risk levels and AML review dates",
    "aml-reviews-due": "AML reviews due in the next N days",
    "aml-reviews-expired": "AML review expired",
    "prospects-assigned": "Prospects assigned for a period",
    "prospects-unassigned": "Unassigned prospects (ageing)",
    "rejected-with-rm": "Clients in Rejected status (ageing)",
    "amendments": "Clients static data amendments",
    "invoices-onboarding": "Onboarding services invoices",
    "invoices-service-requests": "Service request invoices",
    "invoices-pending": "Raising invoices pending",
    "service-requests-ageing": "Service requests status and ageing",
    "data-quality": "Client data to correct",
    "visits-recorded": "Calls / visits recorded (date range)",
    "visits-not-done": "Clients with no call / visit (date range)",
}


# Triam UAT 19-11-2026: who may run these reports (Administrators always may). The amendments report is for
# Compliance (CO) and the Approver; the invoice and service request reports for the Accountant (invoice.manage) and
# the Sales Manager (a role seeing its department's clients, view.department_clients).
def _compliance_or_approver(user: User) -> bool:
    from app.auth.permissions import has_permission
    return has_permission(user, "client.approve") or has_permission(user, "client.final_approve")


def _accounts_or_sales_manager(user: User) -> bool:
    from app.auth.permissions import has_permission
    return has_permission(user, "invoice.manage") or has_permission(user, "view.department_clients")


RESTRICTED = {
    "amendments": _compliance_or_approver,
    "invoices-onboarding": _accounts_or_sales_manager,
    "invoices-service-requests": _accounts_or_sales_manager,
    "invoices-pending": _accounts_or_sales_manager,
    "service-requests-ageing": _accounts_or_sales_manager,
}


def may_run(user: User, key: str) -> bool:
    """Administrators and Inquiry & Reports (read only, BRD §13: sees everything, changes nothing) may run every
    report (Triam 24-11-2026); the restricted ones are otherwise for their desks."""
    from app.auth.permissions import has_permission
    from app.models import UserRole
    rule = RESTRICTED.get(key)
    return rule is None or user.role == UserRole.ADMIN or has_permission(user, "read_only") or rule(user)


def available(user: User) -> dict:
    return {k: t for k, t in REPORTS.items() if may_run(user, k)}


def run(db: Session, user: User, key: str, days: Optional[int] = None, date_from: Optional[date] = None,
        date_to: Optional[date] = None, status: Optional[str] = None, department_id: Optional[int] = None,
        entity: Optional[str] = None, tag: Optional[str] = None, rm_id: Optional[int] = None,
        request_type: Optional[str] = None, sr_type: Optional[str] = None, account_id: Optional[int] = None) -> dict:
    if days is not None and not 0 <= days <= 3650:
        raise HTTPException(status_code=400, detail="Days must be between 0 and 3650")
    if key in REPORTS and not may_run(user, key):
        raise HTTPException(status_code=403, detail="This report isn't available to your role")
    f = Filters(entity, department_id, tag, rm_id, account_id)
    if key == "visits-recorded":
        return visits_recorded(db, user, date_from, date_to, f)
    if key == "visits-not-done":
        return visits_not_done(db, user, date_from, date_to, f)
    if key == "amendments":
        return amendments_report(db, user, date_from, date_to, f)
    if key == "invoices-onboarding":
        return invoices_report(db, user, "Onboarding", date_from, date_to, f)
    if key == "invoices-service-requests":
        return invoices_report(db, user, "Service Request", date_from, date_to, f)
    if key == "invoices-pending":
        return invoices_pending(db, user, date_from, date_to, request_type, f)
    if key == "service-requests-ageing":
        return service_requests_ageing(db, user, date_from, date_to, sr_type, f)
    if key == "onboarding-approved":
        return onboarding_approved(db, user, date_from, date_to, department_id)
    if key == "onboarding-in-progress":
        return onboarding_in_progress(db, user, date_from, date_to, status, department_id)
    if key == "under-formation":
        return under_formation(db, user, UNDER_FORMATION_DAYS if days is None else days)
    if key == "documents-expiring":
        return documents_expiring(db, user, 30 if days is None else days)
    if key == "documents-expired":
        return documents_expired(db, user)
    if key == "clients-risk":
        return clients_risk(db, user)
    if key == "aml-reviews-due":
        return aml_reviews_due(db, user, 30 if days is None else days)
    if key == "aml-reviews-expired":
        return aml_reviews_expired(db, user)
    if key == "prospects-assigned":
        return prospects_assigned(db, user, date_from, date_to)
    if key == "prospects-unassigned":
        return prospects_unassigned(db, user)
    if key == "data-quality":
        return data_quality(db, user)
    if key == "rejected-with-rm":
        return rejected_with_rm(db, user)
    raise HTTPException(status_code=404, detail="Unknown report")
