"""P6 Engagements — how a company comes to Triam, and bringing existing work into the CRM.

Routes (Case.engagement_route):
  Formation        the existing 11-stage pipeline for a new company.
  Existing Entity  a company Triam already services. Created directly as Active with its real
                   incorporation date and last filing dates; the Filing Calendar is built from
                   that history, so anything overdue shows straight away.
  Transfer In      a company moving from another registered agent. Same CDD / invoice gates as a
                   formation, plus a transfer documents checklist; the two application stages read
                   "Transfer Requested from Previous Agent" and "Transfer Completed" in the UI, and
                   the calendar is built from the company's history when the transfer completes.

Bulk import (admin): existing entities and open service requests from the Excel trackers, with a
dry run that reports, row by row, what would be created, skipped as a duplicate, or rejected.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import jurisdictions
from app.audit import log_event
from app.models import Account, Case, CaseDocument, CaseStage, ComplianceSchedule, CDDRecord, Instruction, User
from app.models.case import Jurisdiction
from app.services import compliance_service, company_service, master_service
from app.utils.uid import next_uid

FORMATION, EXISTING, TRANSFER = "Formation", "Existing Entity", "Transfer In"
ROUTES = (FORMATION, EXISTING, TRANSFER)
PRIOR_KEYS = {"last_renewal_date": "renewal", "last_esr_date": "esr_filing", "last_ar_date": "ar_filing"}

# Documents needed from the outgoing agent for a transfer (Status & Plan, transfer-in proposal).
TRANSFER_DOCUMENTS = [
    "Certificate of Incorporation (transfer)",
    "Memorandum & Articles of Association (transfer)",
    "Register of Members (ROM)",
    "Register of Directors (ROD)",
    "Recent Certificate of Good Standing",
]

ENGAGEMENT_FIELDS = {"engagement_route", "previous_agent", "incorporation_date", "company_number",
                     "registered_agent", *PRIOR_KEYS}


# ─── Creating a case on a route ─────────────────────────────────────────────

def validate_route(data) -> None:
    route = data.engagement_route or FORMATION
    if route not in ROUTES:
        raise HTTPException(status_code=400, detail=f"Unknown engagement route '{route}'")
    if route in (EXISTING, TRANSFER):
        missing = [label for label, v in (("Jurisdiction", data.jurisdiction), ("Incorporation date", data.incorporation_date)) if not v]
        if route == TRANSFER and not (data.previous_agent or "").strip():
            missing.append("Previous registered agent")
        if missing:
            raise HTTPException(status_code=400, detail=f"{route}: {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")
    for key in PRIOR_KEYS:
        d = getattr(data, key, None)
        if d and d > date.today():
            raise HTTPException(status_code=400, detail=f"{key.replace('_', ' ').capitalize()} can't be in the future")


def prior_dates(data) -> Optional[dict]:
    out = {PRIOR_KEYS[k]: getattr(data, k).isoformat() for k in PRIOR_KEYS if getattr(data, k, None)}
    return out or None


def apply_route(db: Session, case: Case, data) -> None:
    """After the case row exists: company details, transfer checklist, starting stage."""
    route = case.engagement_route
    if route == FORMATION:
        return
    profile = company_service.get_or_create(db, case.id)
    profile.incorporation_date = data.incorporation_date
    if data.company_number:
        profile.company_number = data.company_number
    if data.registered_agent:
        profile.registered_agent = data.registered_agent[:50]
    if route == EXISTING:
        case.stage = CaseStage.ACTIVE  # already serviced by Triam; the pipeline doesn't apply
    if route == TRANSFER:
        cdd = db.query(CDDRecord).filter(CDDRecord.case_id == case.id).first()
        if cdd:
            for doc in TRANSFER_DOCUMENTS:
                db.add(CaseDocument(cdd_record_id=cdd.id, doc_type=doc, received=False))


# ─── Filing Calendar from the company's history ─────────────────────────────

def schedule_dates(case: Case, incorporation: Optional[date]) -> dict:
    """Due dates for a fresh schedule. Where the last filing date is known, the next one is due
    after it — which may already be in the past (overdue). Otherwise the usual rule applies."""
    spec = jurisdictions.get(case.jurisdiction)
    base = incorporation or case.license_received_date or date.today()
    prior = {k: date.fromisoformat(v) for k, v in (case.prior_filing_dates or {}).items()}
    out = {}
    history_route = case.engagement_route in (EXISTING, TRANSFER)
    for item in spec.compliance_items:
        last = prior.get(item.key)
        if last:
            due = compliance_service.compute_due(item, incorporation_date=incorporation, base=base, after=last)
        elif history_route and item.anchor == "annual" and incorporation:
            # No last filing date given for an established company: assume it is up to date and
            # take the next anniversary from today, rather than counting from incorporation (which
            # would show years-old filings as overdue).
            due = compliance_service.next_anniversary(incorporation)
        else:
            due = compliance_service.compute_due(item, incorporation_date=incorporation, base=base)
        if due is not None:
            out[f"{item.key}_due_date"] = due
        if item.key != "bo_filing":
            out[f"{item.key}_cadence_months"] = item.cadence_months
        if last:
            out[f"{item.key}_last_completed_date"] = last
    return out


def build_calendar(db: Session, case: Case) -> ComplianceSchedule:
    existing = db.query(ComplianceSchedule).filter(ComplianceSchedule.case_id == case.id).first()
    if existing:
        return existing
    profile = company_service.get_or_create(db, case.id)
    schedule = ComplianceSchedule(case_id=case.id, **schedule_dates(case, profile.incorporation_date))
    db.add(schedule)
    db.flush()
    return schedule


# ─── Bulk import ────────────────────────────────────────────────────────────

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %m %Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y")


def parse_date(value, label: str) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{label} '{s}' is not a date (use DD/MM/YYYY)")


def _money(value, label: str) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        d = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        raise ValueError(f"{label} '{value}' is not a number")
    if d < 0:
        raise ValueError(f"{label} can't be negative")
    return d


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").lower().split())


def _jurisdiction(value) -> str:
    v = (value or "").strip()
    match = next((j.value for j in Jurisdiction if j.value.lower() == v.lower()), None)
    if not match:
        raise ValueError(f"Jurisdiction '{v}' is not recognised ({', '.join(j.value for j in Jurisdiction)})")
    return match


def _find_account(db: Session, client_id: Optional[str], name: Optional[str]) -> Optional[Account]:
    if client_id and client_id.strip():
        acc = db.query(Account).filter(func.lower(Account.client_id) == client_id.strip().lower()).first()
        if not acc:
            raise ValueError(f"No client with Client ID '{client_id.strip()}'")
        return acc
    if name:
        return db.query(Account).filter(func.lower(Account.company_name) == _norm(name)).first()
    return None


def import_entities(db: Session, user: User, rows: list[dict], dry_run: bool) -> list[dict]:
    """Existing entities from the Offshore Entities List ("Active RELs"). Each becomes an Active
    case on the Existing Entity route with its Filing Calendar. This is data migration by an
    administrator, so the cases are recorded as approved (and audited as imported)."""
    users = {u.email.lower(): u for u in db.query(User).all()}
    existing_names = {_norm(n) for (n,) in db.query(Case.company_name).all()}
    from app.models import CompanyProfile
    existing_numbers = {(n or "").strip().lower() for (n,) in db.query(CompanyProfile.company_number).all() if n}
    seen_names, seen_numbers, results = set(), set(), []

    for idx, raw in enumerate(rows):
        r = {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
        name = r.get("company_name") or ""
        res = {"row_index": idx, "company_name": name, "status": "ok", "message": None}
        try:
            if not name:
                raise ValueError("Company name is required")
            jurisdiction = _jurisdiction(r.get("jurisdiction"))
            incorporation = parse_date(r.get("incorporation_date"), "Incorporation date")
            if not incorporation:
                raise ValueError("Incorporation date is required")
            prior = {}
            for col, key in PRIOR_KEYS.items():
                d = parse_date(r.get(col), col.replace("_", " ").capitalize())
                if d:
                    if d > date.today():
                        raise ValueError(f"{col.replace('_', ' ').capitalize()} is in the future")
                    prior[key] = d.isoformat()
            account = _find_account(db, r.get("client_id"), None)
            rm = None
            if r.get("rm_email"):
                rm = users.get(r["rm_email"].lower())
                if not rm:
                    raise ValueError(f"No user with email '{r['rm_email']}'")
            number = (r.get("company_number") or "").lower()
            if _norm(name) in existing_names or _norm(name) in seen_names or (number and (number in existing_numbers or number in seen_numbers)):
                res.update(status="duplicate", message="Already in the CRM (same company name or number)")
                results.append(res)
                continue
        except ValueError as e:
            res.update(status="error", message=str(e))
            results.append(res)
            continue

        seen_names.add(_norm(name))
        if number:
            seen_numbers.add(number)
        if not dry_run:
            case = Case(case_uid=next_uid(db, Case, "case_uid", "CASE"), company_name=name, jurisdiction=jurisdiction,
                        service_type=r.get("service_type") or None, notes=r.get("notes") or None,
                        account_id=account.id if account else None,
                        rm_id=(rm.id if rm else (account.spoc_id if account else None)),
                        engagement_route=EXISTING, stage=CaseStage.ACTIVE, compliance_status="Approved",
                        prior_filing_dates=prior or None)
            db.add(case)
            db.flush()
            db.add(CDDRecord(case_id=case.id))
            profile = company_service.get_or_create(db, case.id)
            profile.incorporation_date = incorporation
            profile.company_number = r.get("company_number") or None
            profile.registered_agent = (r.get("registered_agent") or "")[:50] or None
            db.flush()
            build_calendar(db, case)
            log_event(db, "import", f"Existing entity {case.case_uid} ({name}) imported", subject_type="Case",
                      subject_id=case.id, account_id=case.account_id, changes={"row": idx + 1})
            res["case_id"] = case.id
        results.append(res)

    if not dry_run:
        db.commit()
    return results


def import_service_requests(db: Session, user: User, rows: list[dict], dry_run: bool) -> list[dict]:
    """Open service requests from the Excel Instruction Tracker, matched to a client (by Client ID
    or exact name) and optionally a case (by Case ID or exact company name)."""
    active_types = master_service.active_codes(db, "service_request_type")
    statuses = {"pending": "Pending", "in progress": "In Progress", "completed": "Completed", "on hold": "On Hold"}
    results = []
    for idx, raw in enumerate(rows):
        r = {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
        name = r.get("company_name") or r.get("client_id") or ""
        res = {"row_index": idx, "company_name": name, "status": "ok", "message": None}
        try:
            rtype = r.get("request_type") or ""
            if not rtype:
                raise ValueError("Request type is required")
            if active_types and rtype not in active_types:
                raise ValueError(f"Request type '{rtype}' is not in the Service Request Types list")
            status = statuses.get((r.get("status") or "Pending").lower())
            if not status:
                raise ValueError(f"Status '{r.get('status')}' must be Pending, In Progress, Completed or On Hold")
            case = None
            if r.get("case_uid"):
                case = db.query(Case).filter(func.lower(Case.case_uid) == r["case_uid"].lower()).first()
                if not case:
                    raise ValueError(f"No case '{r['case_uid']}'")
            account = _find_account(db, r.get("client_id"), r.get("company_name"))
            if case is None and r.get("company_name"):
                case = db.query(Case).filter(func.lower(Case.company_name) == _norm(r["company_name"])).first()
            if account is None and case is not None:
                account = db.get(Account, case.account_id) if case.account_id else None
            if account is None and case is None:
                raise ValueError("No matching client or case (give a Client ID, Case ID or the exact company name)")
            if account and case and case.account_id and case.account_id != account.id:
                raise ValueError("The case belongs to a different client")
            values = dict(
                instruction_type=rtype, status=status,
                date_received=parse_date(r.get("date_received"), "Date received"),
                date_sent_to_vistra=parse_date(r.get("date_sent_to_vistra"), "Date sent to Vistra"),
                date_received_from_vistra=parse_date(r.get("date_received_from_vistra"), "Date received from Vistra"),
                date_completed=parse_date(r.get("date_completed"), "Date completed"),
                cost_amount=_money(r.get("cost_amount"), "Cost"), charge_amount=_money(r.get("charge_amount"), "Charge"),
                invoice_reference=r.get("invoice_reference") or None, comments=r.get("comments") or None,
            )
        except ValueError as e:
            res.update(status="error", message=str(e))
            results.append(res)
            continue
        res["company_name"] = (account.company_name if account else case.company_name)
        if not dry_run:
            inst = Instruction(account_id=account.id if account else None, case_id=case.id if case else None, **values)
            db.add(inst)
            db.flush()
            log_event(db, "import", f"Service request '{rtype}' for {res['company_name']} imported", subject_type="Instruction",
                      subject_id=inst.id, account_id=inst.account_id, changes={"row": idx + 1})
            res["instruction_id"] = inst.id
        results.append(res)
    if not dry_run:
        db.commit()
    return results
