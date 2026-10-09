"""Service layer: Account business logic."""
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from fastapi import HTTPException
from typing import Optional
from decimal import Decimal
from datetime import date, datetime, timezone
from dateutil.relativedelta import relativedelta

from app.models import Account, Priority, User, UserRole, Case, CaseStatus, Invoice, InvoiceLedgerStatus, ClientIdSequence
from app.auth.permissions import has_permission
from app.audit import log_event
from app.schemas.account import AccountCreate, AccountUpdate, AccountImportRow, AccountImportRowResult, AccountBulkUpdateRequest, BulkUpdateResult
from app.utils.uid import next_uid
from app.utils.fuzzy_match import top_matches
from app.services import compliance_service, access_control, master_service, client_workflow_service

# Client-database spec §24.6 — review cadence by risk rating.
_AML_REVIEW_CADENCE_YEARS = {"High": 1, "Medium": 2, "Low": 3}


# Account field -> (master list, label, kind). kind: "one" | "many" (JSON list) | "csv" (comma string).
_MASTER_FIELDS = {
    "anchor_entity": ("triam_entity", "Anchor Triam Entity", "one"),
    "non_anchor_entities": ("triam_entity", "Non-anchor Triam Entities", "many"),
    "services_obtained": ("service", "Services obtained", "many"),
    "nature_of_services_sought": ("service", "Nature of Services Sought", "many"),
    "tags": ("tag", "Tags", "csv"),
    "regulator_name": ("regulator", "Name of Regulator", "one"),
    "licensing_authority": ("licensing_authority", "Licensing Authority", "one"),
}


def _as_list(value, kind) -> list:
    if value in (None, "", []):
        return []
    if kind == "csv":
        return [t.strip() for t in str(value).split(",") if t.strip()]
    if kind == "one":
        return [value]
    return list(value)


def _validate_master_fields(db: Session, payload: dict, existing: Optional[Account] = None) -> None:
    """BRD §4/§18 — values must come from the active admin-managed lists. A value the record
    already holds stays valid even if its master item was later deactivated (so old clients
    remain editable)."""
    for field, (list_type, label, kind) in _MASTER_FIELDS.items():
        if field not in payload:
            continue
        new_values = _as_list(payload[field], kind)
        kept = set(_as_list(getattr(existing, field, None), kind)) if existing else set()
        master_service.assert_valid(db, list_type, [v for v in new_values if v not in kept], label)


# ─── BRD §3 search name / duplicates, §19 Client ID, §11 status timestamp ─────

def _norm(name: Optional[str]) -> str:
    return " ".join((name or "").split()).lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _same_name_query(db: Session, company_name: str, exclude_id: Optional[int] = None):
    q = db.query(Account).filter(func.lower(func.trim(Account.company_name)) == _norm(company_name))
    if exclude_id:
        q = q.filter(Account.id != exclude_id)
    return q


def _search_name_taken(db: Session, search_name: str, exclude_id: Optional[int] = None) -> bool:
    q = db.query(Account.id).filter(func.lower(Account.search_name) == _norm(search_name))
    if exclude_id:
        q = q.filter(Account.id != exclude_id)
    return q.first() is not None


def _default_search_name(db: Session, company_name: str, anchor_entity: Optional[str]) -> str:
    """Prefill from the legal name; if that's taken (only possible via the duplicate exception),
    disambiguate with the entity and then a counter."""
    base = " ".join(company_name.split())[:100]
    candidates = [base]
    if anchor_entity:
        candidates.append(f"{base} ({anchor_entity})")
    candidates += [f"{base} ({n})" for n in range(2, 50)]
    for c in candidates:
        if not _search_name_taken(db, c):
            return c
    raise HTTPException(status_code=400, detail="Please enter a Unique Search Name — the default is already taken")


def next_client_id(db: Session, entity_code: str) -> str:
    """BRD §19 — {ENTITY}/{00000}, separate counter per entity. The counter row is locked so
    concurrent saves can't take the same number (FOR UPDATE is a no-op on SQLite, used in tests)."""
    seq = db.query(ClientIdSequence).filter(ClientIdSequence.entity_code == entity_code).with_for_update().first()
    if seq is None:
        # First ID for this entity — start after any IDs already present (e.g. data fixed by hand),
        # so the counter can never hand out a number that's taken.
        prefix = f"{entity_code}/"
        existing = [cid for (cid,) in db.query(Account.client_id).filter(Account.client_id.like(f"{prefix}%")).all()]
        highest = max((int(c[len(prefix):]) for c in existing if c[len(prefix):].isdigit()), default=0)
        seq = ClientIdSequence(entity_code=entity_code, last_value=highest)
        db.add(seq)
        db.flush()
    while True:
        seq.last_value += 1
        candidate = f"{entity_code}/{seq.last_value:05d}"
        if not db.query(Account.id).filter(Account.client_id == candidate).first():
            return candidate


def lookup_by_name(db: Session, user: User, q: str, exclude_id: Optional[int] = None, limit: int = 10) -> list[dict]:
    """BRD §3 — from the 3rd letter, list existing clients whose legal or search name has a word
    starting with what was typed. Searches *all* clients (a duplicate is a duplicate even if another
    RM owns it) but returns only the name and ID for clients the user can't open."""
    term = _norm(q)
    if len(term) < 3:
        return []
    like_start, like_word = f"{term}%", f"% {term}%"
    query = db.query(Account).filter(or_(
        func.lower(Account.company_name).like(like_start), func.lower(Account.company_name).like(like_word),
        func.lower(Account.search_name).like(like_start), func.lower(Account.search_name).like(like_word),
    ))
    if exclude_id:
        query = query.filter(Account.id != exclude_id)
    out = []
    for acc in query.order_by(Account.company_name).limit(limit).all():
        can_open = access_control.user_can_access_account(db, acc, user)
        out.append({
            "id": acc.id,
            "client_id": acc.client_id,
            "company_name": acc.company_name,
            "search_name": acc.search_name,
            "account_type": acc.account_type,
            "exact_match": _norm(acc.company_name) == term,
            "can_open": can_open,
            "profile_status": acc.profile_status if can_open else None,
        })
    return out


def _set_status(acc: Account, user: User) -> None:
    acc.status_updated_at = _now()
    acc.status_updated_by_id = user.id


def _compute_next_aml_review_date(acc: Account) -> None:
    """Recompute Account.next_aml_review_date from risk_rating + cdd_completion_date.

    Server-computed, not user-editable — cleared if either input is missing.
    """
    years = _AML_REVIEW_CADENCE_YEARS.get(acc.risk_rating or "")
    if acc.cdd_completion_date and years:
        acc.next_aml_review_date = acc.cdd_completion_date + relativedelta(years=years)
    else:
        acc.next_aml_review_date = None


def list_accounts(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    priority: Optional[str] = None,
) -> tuple[list[Account], int]:
    query = db.query(Account)
    # BRD §15 RM privacy + supervisor visibility (was: RMs saw only clients they created).
    visibility = access_control.account_visibility_clause(db, user)
    if visibility is not None:
        query = query.filter(visibility)

    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Account.company_name.ilike(pattern),
            Account.key_contacts.ilike(pattern),
            Account.account_uid.ilike(pattern),
        ))
    if industry:
        query = query.filter(Account.industry == industry)
    if country:
        query = query.filter(Account.country == country)
    if priority:
        query = query.filter(Account.strategic_priority == priority)

    total = query.count()
    items = query.order_by(Account.total_invoiced_amount.desc()).offset(skip).limit(limit).all()
    return items, total


def find_similar_accounts(db: Session, name: str, exclude_id: Optional[int] = None) -> list[tuple[int, str, int]]:
    query = db.query(Account.id, Account.company_name)
    if exclude_id:
        query = query.filter(Account.id != exclude_id)
    return top_matches(name, query.all())


def get_account(db: Session, account_id: int, user: User) -> Account:
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if not access_control.user_can_access_account(db, acc, user):
        raise HTTPException(status_code=403, detail="Access denied")
    return acc


def _assert_shareholder_ownership_complete(account: Account) -> None:
    """Client spec §20 — Shareholder effective ownership must total 100% before a Corporate
    profile can be finalized (moved to Approved/Active). Individual accounts are exempt —
    there's no Shareholder concept for a person."""
    if account.account_type != "Corporate":
        return
    total = sum((p.effective_ownership_percent or Decimal("0")) for p in account.parties if p.party_role == "Shareholder")
    if abs(total - Decimal("100")) > Decimal("0.01"):
        raise HTTPException(
            status_code=400,
            detail=f"Shareholder effective ownership must total 100% before the profile can be Approved/Active (currently {total}%).",
        )


def _assert_date_sanity(data) -> None:
    """Client spec CRM-change-request items 7 & 11 — Incorporation Date can't be in the
    future; License Expiry Date can't be in the past. Interactive create/update only —
    CSV import of historical data is exempt, since expired licenses are legitimate there."""
    today = date.today()
    incorporation_date = getattr(data, "incorporation_date", None)
    if incorporation_date and incorporation_date > today:
        raise HTTPException(status_code=400, detail="Incorporation Date cannot be in the future")
    license_expiry_date = getattr(data, "license_expiry_date", None)
    if license_expiry_date and license_expiry_date < today:
        raise HTTPException(status_code=400, detail="License Expiry Date cannot be before today")


def _normalize_non_anchor_rms(acc: Account) -> None:
    """Client spec §I — the Anchor RM (spoc_id) can't also be a Non-anchor RM. Enforced
    server-side too, since bulk-update can change the anchor without touching the list."""
    if acc.non_anchor_rm_ids:
        acc.non_anchor_rm_ids = list(dict.fromkeys(i for i in acc.non_anchor_rm_ids if i != acc.spoc_id)) or None


def create_account(db: Session, data: AccountCreate, user: User) -> Account:
    # BRD §3 — an ordinary duplicate is blocked; an approver may create it with a recorded reason.
    existing = _same_name_query(db, data.company_name).first()
    override_reason = None
    if existing:
        if not data.allow_duplicate:
            raise HTTPException(status_code=409, detail=f"A client named '{existing.company_name}' already exists ({existing.client_id or existing.account_uid}). An approver can create it anyway with a reason.")
        if not has_permission(user, "client.approve"):
            raise HTTPException(status_code=403, detail="Only an approver (CO / MLRO / Admin) can create a duplicate client")
        override_reason = (data.duplicate_reason or "").strip()
        if len(override_reason) < 10:
            raise HTTPException(status_code=400, detail="Give a meaningful reason (at least 10 characters) for creating a duplicate client")

    # BRD §19 — the Client ID is built from the Anchor Triam Entity (issued at Compliance approval).
    if not (data.anchor_entity or "").strip():
        raise HTTPException(status_code=400, detail="Anchor Triam Entity is required — it determines the Client ID")

    search_name = data.search_name
    if search_name:
        if _search_name_taken(db, search_name):
            raise HTTPException(status_code=400, detail=f"Unique Search Name '{search_name}' is already used by another client")
    else:
        search_name = _default_search_name(db, data.company_name, data.anchor_entity)

    _assert_date_sanity(data)
    if any(getattr(data, f, None) not in (None, "") for f in CDD_FIELDS) and not has_permission(user, "client.cdd_edit"):
        raise HTTPException(status_code=403, detail="Only Compliance (MLRO) can complete the CDD / risk assessment section")

    owner_id = data.owner_id or user.id
    payload = data.model_dump(exclude={"owner_id", "allow_duplicate", "duplicate_reason", "search_name"})
    payload["profile_status"] = client_workflow_service.NEW  # BRD §11 — status only moves via the workflow
    _validate_master_fields(db, payload)
    acc = Account(
        account_uid=next_uid(db, Account, "account_uid", "ACC"),
        search_name=search_name,
        duplicate_override_reason=override_reason,
        **payload,
        owner_id=owner_id,
    )
    _set_status(acc, user)
    _compute_next_aml_review_date(acc)
    _normalize_non_anchor_rms(acc)
    db.add(acc)
    db.flush()
    if override_reason:
        log_event(db, "duplicate_override", f"Duplicate client '{acc.company_name}' created by exception: {override_reason}",
                  subject_type="Account", subject_id=acc.id, account_id=acc.id,
                  changes={"existing_client": existing.client_id or existing.account_uid, "reason": override_reason})
    db.commit()
    db.refresh(acc)
    return acc


# Triam BRD mark-up §7/§11: the CDD / risk assessment section is completed only by Compliance (MLRO).
CDD_FIELDS = ("risk_rating", "aml_classification", "edd_reason", "kyc_verified_by", "cdd_completion_date")


def update_account(db: Session, account_id: int, data: AccountUpdate, user: User):
    """Save a section of the client profile.

    Before approval the change applies directly. Once the client is approved (BRD §13) the change is
    staged in the user's open amendment instead and only reaches the live record when Compliance
    approves it — the staged view of the client is returned so the form keeps showing it."""
    acc = get_account(db, account_id, user)
    if _compliance_cdd_save(db, acc, data, user):
        return acc
    client_workflow_service.assert_editable(acc)
    from app.services import amendment_service  # local: amendment_service imports this module
    if amendment_service.is_amendable(acc):
        return amendment_service.stage_account_update(db, acc, data, user)
    update_data = apply_update(db, acc, data, user)
    if update_data:
        client_workflow_service.note_edit(acc, user)
    db.commit()
    db.refresh(acc)
    return acc


def _compliance_cdd_save(db: Session, acc: Account, data: AccountUpdate, user: User) -> bool:
    """While a new client is at the Compliance step the profile is locked, except that Compliance
    completes the CDD section. Returns True when this save was that case (and is done)."""
    if acc.profile_status != client_workflow_service.AWAITING:
        return False
    fields = set(data.model_dump(exclude_unset=True))
    req = client_workflow_service.pending_request(db, acc.id)
    if not fields or not fields <= set(CDD_FIELDS) or client_workflow_service.stage_of(req) != client_workflow_service.STAGE_COMPLIANCE \
            or not has_permission(user, "client.cdd_edit"):
        return False
    before = {f: getattr(acc, f) for f in fields}
    apply_update(db, acc, data, user)
    changed = {f: {"old": str(before[f]) if before[f] is not None else None, "new": str(getattr(acc, f)) if getattr(acc, f) is not None else None}
               for f in fields if before[f] != getattr(acc, f)}
    if changed:
        log_event(db, "cdd_update", f"CDD section of {acc.company_name} completed by Compliance", subject_type="Account",
                  subject_id=acc.id, account_id=acc.id, changes=changed)
    db.commit()
    db.refresh(acc)
    return True


def apply_update(db: Session, acc: Account, data: AccountUpdate, user: User) -> dict:
    """Validate and apply a profile update to `acc` without committing. Shared by direct saves and
    by amendments (staged on save, then applied for real when Compliance approves)."""
    _assert_date_sanity(data)
    update_data = data.model_dump(exclude_unset=True)
    if user.role == UserRole.RM:
        update_data.pop("owner_id", None)
    # BRD §11/§15 — status changes only through Submit / Approve / Reject / status actions.
    requested_status = update_data.pop("profile_status", None)
    if requested_status is not None and requested_status != acc.profile_status:
        raise HTTPException(status_code=400, detail="Status can't be edited directly — use Submit / Approve / Reject or the status actions on the client profile")
    cdd_changes = [f for f in CDD_FIELDS if f in update_data and update_data[f] != getattr(acc, f)]
    if cdd_changes and not has_permission(user, "client.cdd_edit"):
        raise HTTPException(status_code=403, detail="Only Compliance (MLRO) can complete the CDD / risk assessment section")
    _validate_master_fields(db, update_data, existing=acc)
    if "search_name" in update_data:
        if not update_data["search_name"]:
            raise HTTPException(status_code=400, detail="Unique Search Name can't be empty")
        if _search_name_taken(db, update_data["search_name"], exclude_id=acc.id):
            raise HTTPException(status_code=400, detail=f"Unique Search Name '{update_data['search_name']}' is already used by another client")
    if update_data.get("company_name") and _norm(update_data["company_name"]) != _norm(acc.company_name):
        clash = _same_name_query(db, update_data["company_name"], exclude_id=acc.id).first()
        if clash:
            raise HTTPException(status_code=409, detail=f"A client named '{clash.company_name}' already exists ({clash.client_id or clash.account_uid})")
    for field, value in update_data.items():
        setattr(acc, field, value)
    # The Client ID is issued when Compliance approves a new client (Triam mark-up §18); until then the
    # temporary ID is shown. Approved clients that pre-date Client IDs get one on their next save.
    # Once issued, a Client ID never changes (even if the Anchor Entity later does).
    if not acc.client_id and acc.anchor_entity and acc.profile_status not in (
            client_workflow_service.NEW, client_workflow_service.WIP, client_workflow_service.AWAITING):
        acc.client_id = next_client_id(db, acc.anchor_entity)
    if not acc.search_name:
        acc.search_name = _default_search_name(db, acc.company_name, acc.anchor_entity)
    if "risk_rating" in update_data or "cdd_completion_date" in update_data:
        _compute_next_aml_review_date(acc)
    _normalize_non_anchor_rms(acc)
    return update_data


def bulk_update_accounts(db: Session, user: User, data: AccountBulkUpdateRequest) -> list[BulkUpdateResult]:
    patch_fields = {k: v for k, v in data.model_dump(exclude={"ids"}).items() if v is not None}
    patch = AccountUpdate(**patch_fields)
    results = []
    for account_id in data.ids:
        try:
            update_account(db, account_id, patch, user)
            results.append(BulkUpdateResult(id=account_id, status="ok"))
        except HTTPException as e:
            results.append(BulkUpdateResult(id=account_id, status="error", message=e.detail))
    return results


def build_track_record(db: Session, account: Account) -> dict:
    """Client-facing summary of an account's relationship history — cases, compliance, invoicing, parties."""
    excluded_statuses = compliance_service.DORMANT_CASE_STATUSES | {CaseStatus.REJECTED.value}
    cases = account.cases
    case_ids = [c.id for c in cases]

    ledger = db.query(Invoice).filter(Invoice.case_id.in_(case_ids)).all() if case_ids else []
    ledger_paid = sum((inv.amount for inv in ledger if inv.status == InvoiceLedgerStatus.PAID.value), start=0)
    ledger_outstanding = sum((inv.amount for inv in ledger if inv.status != InvoiceLedgerStatus.PAID.value), start=0)

    case_rows = []
    for c in cases:
        schedule = c.compliance_schedule
        case_rows.append({
            "case_uid": c.case_uid,
            "company_name": c.company_name,
            "jurisdiction": c.jurisdiction,
            "service_type": c.service_type,
            "stage": c.stage.value if hasattr(c.stage, "value") else c.stage,
            "status": c.status,
            "onboarding_date": c.onboarding_date,
            "invoice_status": c.invoice_status.value if hasattr(c.invoice_status, "value") else c.invoice_status,
            "invoice_amount": c.invoice_amount,
            "next_renewal_due": schedule.renewal_due_date if schedule else None,
            "next_esr_due": schedule.esr_filing_due_date if schedule else None,
            "next_ar_due": schedule.ar_filing_due_date if schedule else None,
            "next_bo_due": schedule.bo_filing_due_date if schedule else None,
        })

    party_rows = [
        {
            "full_name": p.full_name,
            "party_role": p.party_role,
            "constitution": p.constitution,
            "effective_ownership_percent": p.effective_ownership_percent,
        }
        for p in account.parties
    ]

    return {
        "account_uid": account.account_uid,
        "company_name": account.company_name,
        "account_type": account.account_type,
        "industry": account.industry,
        "country": account.country,
        "risk_rating": account.risk_rating,
        "kyc_status": account.kyc_status,
        "client_since": account.created_at,
        "total_cases": account.total_cases,
        "active_cases": sum(1 for c in cases if c.status not in excluded_statuses),
        "total_onboarding_invoiced": account.total_invoiced_amount,
        "ledger_invoices_paid": ledger_paid,
        "ledger_invoices_outstanding": ledger_outstanding,
        "cases": case_rows,
        "parties": party_rows,
    }


def delete_account(db: Session, account_id: int, user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Admin can delete accounts")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()


def import_accounts(
    db: Session, user: User, rows: list[AccountImportRow], dry_run: bool,
) -> list[AccountImportRowResult]:
    existing_names = {_norm(name) for (name,) in db.query(Account.company_name).all()}
    seen_in_batch: set[str] = set()
    results: list[AccountImportRowResult] = []

    for idx, row in enumerate(rows):
        name = (row.company_name or "").strip()
        if not name:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="error", message="Company name is required"))
            continue
        if _norm(name) in existing_names or _norm(name) in seen_in_batch:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="duplicate", message="Client with this company name already exists"))
            continue

        seen_in_batch.add(_norm(name))
        if dry_run:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="ok"))
            continue

        payload = row.model_dump(exclude_none=True)
        payload["company_name"] = name
        # strategic_priority is a DB-level enum — an unrecognized CSV value would fail at
        # insert time, so normalize case-insensitively and drop it (falls back to the
        # column default) rather than let the whole row error out.
        raw_priority = payload.pop("strategic_priority", None)
        if raw_priority:
            matched = next((p for p in Priority if p.value.lower() == raw_priority.strip().lower()), None)
            if matched:
                payload["strategic_priority"] = matched
        search_name = payload.pop("search_name", None)
        if search_name and _search_name_taken(db, search_name):
            search_name = None  # fall back to a generated one rather than failing the row
        acc = Account(
            account_uid=next_uid(db, Account, "account_uid", "ACC"),
            owner_id=user.id,
            **payload,
        )
        acc.search_name = search_name or _default_search_name(db, name, acc.anchor_entity)
        if acc.anchor_entity:
            acc.client_id = next_client_id(db, acc.anchor_entity)
        _set_status(acc, user)
        _normalize_non_anchor_rms(acc)
        db.add(acc)
        db.flush()
        results.append(AccountImportRowResult(row_index=idx, company_name=name, status="ok", account_id=acc.id))

    if not dry_run:
        db.commit()

    return results


# ─── BRD §5 / §9 / §10 / §11 mandatory-field checklist ──────────────────────────
# Sections are saved one at a time, so "mandatory" can't be enforced on every save. This list
# drives the on-screen checklist now and becomes a hard block at Submit (P2, BRD §12 step 11).

def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, dict)) and not v)


def missing_mandatory(account: Account) -> list[dict]:
    missing: list[dict] = []

    def need(section, field, label, value=None, when=True):
        if when and _blank(getattr(account, field) if value is None else value):
            missing.append({"section": section, "field": field, "label": label})

    # §4 Triam assignment — common to both types.
    need("Triam assignment", "anchor_entity", "Anchor Triam Entity")
    need("Triam assignment", "services_obtained", "Services obtained")
    need("Triam assignment", "spoc_id", "Anchor RM")
    need("Client info", "search_name", "Unique Search Name")

    if account.account_type == "Individual":
        # §9
        need("Individual details", "company_name", "Full Name")
        need("Individual details", "date_of_birth", "Date of Birth")
        need("Individual details", "passport_expiry_date", "Passport Expiry Date")
        need("Individual details", "country_of_birth", "Country of Birth")
        need("Individual details", "nationality", "Nationality")
        need("Individual details", "country_of_residence", "Country of Residence")
    else:
        # §5 — incorporation date may be blank for a new company formation.
        forming = "Company Formation" in (account.services_obtained or [])
        need("Client info", "company_name", "Client Name")
        need("Client info", "country", "Country of Incorporation / Registration")
        need("Client info", "registration_number", "Incorporation Certificate No.", when=not forming)
        need("Client info", "incorporation_date", "Incorporation Date", when=not forming)
        need("Client info", "license_number", "Trade / Commercial License Number", when=not forming)
        need("Licensing & Regulatory", "licensing_authority", "Licensing Authority", when=not forming)
        need("Licensing & Regulatory", "licensing_authority_other", "Licensing Authority (Other) details",
             when=account.licensing_authority == "Other")
        need("Licensing & Regulatory", "license_start_date", "License Start / Registration Date", when=not forming)
        need("Licensing & Regulatory", "license_expiry_date", "License Expiry Date", when=not forming)
        need("Licensing & Regulatory", "license_activities", "License Activities", when=not forming)
        need("Licensing & Regulatory", "is_regulated", "Is entity regulated (Yes / No)")
        need("Licensing & Regulatory", "regulator_name", "Name of Regulator", when=account.is_regulated)
        need("Licensing & Regulatory", "regulator_other", "Other Regulator details",
             when=account.is_regulated and account.regulator_name == "Other")
        need("Licensing & Regulatory", "license_category", "License Category", when=account.is_regulated)
        need("Licensing & Regulatory", "regulatory_license_expiry_date", "Current regulatory license expiry",
             when=account.is_regulated)
        need("Tax", "financial_year_end", "Financial Year End")
        need("Tax", "corp_tax_registered", "Corporate Tax Registered (Yes / No)")
        need("Tax", "corp_tax_registration_number", "Corp Tax Registration No.", when=account.corp_tax_registered)
        need("Introducer", "has_introducer", "Introducer (Yes / No)")
        need("Introducer", "introducer_name", "Introducer Name", when=account.has_introducer)

        # §6 — shareholders must exist and add up to 100%.
        shareholders = [p for p in account.parties if p.party_role == "Shareholder"]
        if not shareholders:
            missing.append({"section": "Shareholders / UBOs", "field": "parties", "label": "At least one Shareholder / UBO"})
        else:
            total = sum((Decimal(str(p.effective_ownership_percent or 0)) for p in shareholders), Decimal("0"))
            if abs(total - Decimal("100")) > Decimal("0.01"):
                missing.append({"section": "Shareholders / UBOs", "field": "parties",
                                "label": f"Shareholding must total 100% (currently {total}%)"})

    # §10 KYC / AML is completed by Compliance after submission — see missing_cdd.

    # §11 engagement
    need("Profile Status & Engagement", "engagement_letter_valid_until", "Engagement Letter valid upto",
         when=account.engagement_letter_signed)
    return missing


def missing_cdd(account: Account) -> list[dict]:
    """Triam BRD mark-up §10 — the CDD section Compliance (MLRO) must complete before approving.
    (The AML Risk Level Standard / SDD / EDD was removed; EDD applies to High-risk clients.)"""
    missing: list[dict] = []

    def need(field, label, when=True):
        if when and _blank(getattr(account, field)):
            missing.append({"section": "Customer Risk Assessment / KYC & AML", "field": field, "label": label})

    need("risk_rating", "CDD/AML Risk Level")
    need("edd_reason", "Reason for EDD", when=account.risk_rating == "High")
    need("kyc_verified_by", "KYC Verification performed by")
    need("cdd_completion_date", "CDD Completion Date")
    return missing
