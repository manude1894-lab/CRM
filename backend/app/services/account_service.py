"""Service layer: Account business logic."""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from typing import Optional
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta

from app.models import Account, Priority, User, UserRole, Case, CaseStatus, Invoice, InvoiceLedgerStatus
from app.schemas.account import AccountCreate, AccountUpdate, AccountImportRow, AccountImportRowResult, AccountBulkUpdateRequest, BulkUpdateResult
from app.utils.uid import next_uid
from app.utils.fuzzy_match import top_matches
from app.services import compliance_service

# Client-database spec §24.6 — review cadence by risk rating.
_AML_REVIEW_CADENCE_YEARS = {"High": 1, "Medium": 2, "Low": 3}


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
    if user.role == UserRole.RM:
        query = query.filter(Account.owner_id == user.id)

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
    if user.role == UserRole.RM and acc.owner_id != user.id:
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
    existing = db.query(Account).filter(Account.company_name == data.company_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Account with this company name already exists")

    if data.account_type != "Individual" and not (data.industry or "").strip():
        raise HTTPException(status_code=400, detail="Industry is required")

    _assert_date_sanity(data)

    if data.account_type == "Corporate" and data.profile_status in ("Approved", "Active"):
        # A brand-new account has no parties yet, so ownership can never be complete at creation time.
        raise HTTPException(
            status_code=400,
            detail="Shareholder effective ownership must total 100% before the profile can be Approved/Active (currently 0%).",
        )

    owner_id = data.owner_id or user.id
    payload = data.model_dump(exclude={"owner_id"})
    acc = Account(
        account_uid=next_uid(db, Account, "account_uid", "ACC"),
        **payload,
        owner_id=owner_id,
    )
    _compute_next_aml_review_date(acc)
    _normalize_non_anchor_rms(acc)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def update_account(db: Session, account_id: int, data: AccountUpdate, user: User) -> Account:
    acc = get_account(db, account_id, user)
    _assert_date_sanity(data)
    update_data = data.model_dump(exclude_unset=True)
    if user.role == UserRole.RM:
        update_data.pop("owner_id", None)
    if update_data.get("profile_status") in ("Approved", "Active"):
        _assert_shareholder_ownership_complete(acc)
    for field, value in update_data.items():
        setattr(acc, field, value)
    if "risk_rating" in update_data or "cdd_completion_date" in update_data:
        _compute_next_aml_review_date(acc)
    _normalize_non_anchor_rms(acc)
    db.commit()
    db.refresh(acc)
    return acc


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
    existing_names = {name for (name,) in db.query(Account.company_name).all()}
    seen_in_batch: set[str] = set()
    results: list[AccountImportRowResult] = []

    for idx, row in enumerate(rows):
        name = (row.company_name or "").strip()
        if not name:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="error", message="Company name is required"))
            continue
        if name in existing_names or name in seen_in_batch:
            results.append(AccountImportRowResult(row_index=idx, company_name=name, status="duplicate", message="Client with this company name already exists"))
            continue

        seen_in_batch.add(name)
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
        acc = Account(
            account_uid=next_uid(db, Account, "account_uid", "ACC"),
            owner_id=user.id,
            **payload,
        )
        _normalize_non_anchor_rms(acc)
        db.add(acc)
        db.flush()
        results.append(AccountImportRowResult(row_index=idx, company_name=name, status="ok", account_id=acc.id))

    if not dry_run:
        db.commit()

    return results
