"""Service layer: AccountParty (Shareholders/Directors/Authorised Signatories on a Client)."""
import re
from decimal import Decimal

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Account, AccountParty, User
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_service, client_workflow_service


def _get_account_for_write(db: Session, account_id: int, user: User) -> Account:
    # Reuses account_service.get_account — same 404 + visibility check, no duplication.
    account = account_service.get_account(db, account_id, user)
    client_workflow_service.assert_editable(account)  # locked while awaiting approval (BRD §12)
    client_workflow_service.note_edit(account, user)  # New -> WIP on first change (BRD §11)
    return account


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_party(account: Account, p: AccountParty) -> None:
    """BRD §6–8 rules for one party record, checked on every save (a party is saved as a whole).

    - Shareholders: contact mobile (country code + number) and email are mandatory (BRD §6).
    - Any email given must be a valid address.
    - Effective ownership: 0–100 with at most 2 decimals, and the shareholders' total may not
      exceed 100% ("add Shareholders/UBOs until total ownership reaches 100%").
    """
    if p.email and not _EMAIL_RE.match(p.email.strip()):
        raise HTTPException(status_code=400, detail="Contact Email is not a valid email address")
    if p.party_role == "Shareholder":
        missing = [label for label, value in (
            ("Contact Mobile country code", p.mobile_country_code),
            ("Contact Mobile number", p.mobile_number),
            ("Contact Email", p.email),
        ) if not (value or "").strip()]
        if missing:
            raise HTTPException(status_code=400, detail=f"Shareholder {', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required")
        pct = p.effective_ownership_percent
        if pct is None:
            raise HTTPException(status_code=400, detail="Shareholder Effective Ownership Share (%) is required")
        pct = Decimal(str(pct))
        if pct <= 0 or pct > 100 or pct != pct.quantize(Decimal("0.01")):
            raise HTTPException(status_code=400, detail="Effective Ownership Share must be more than 0 and at most 100, with up to 2 decimals")
        others = sum((Decimal(str(o.effective_ownership_percent or 0)) for o in account.parties
                      if o.party_role == "Shareholder" and o is not p and o.id != p.id), Decimal("0"))
        if others + pct > Decimal("100"):
            raise HTTPException(status_code=400, detail=f"Total shareholding would be {others + pct}% — it can't exceed 100% (other shareholders hold {others}%)")


def _recompute_pep(db: Session, account: Account) -> None:
    account.is_pep = any(p.is_pep for p in account.parties)
    db.commit()


def list_parties(db: Session, account_id: int) -> list[AccountParty]:
    return db.query(AccountParty).filter(AccountParty.account_id == account_id).order_by(AccountParty.id).all()


def get_party(db: Session, party_id: int) -> AccountParty:
    p = db.query(AccountParty).filter(AccountParty.id == party_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Party not found")
    return p


def create_party(db: Session, account_id: int, data: AccountPartyCreate, user: User) -> AccountParty:
    account = _get_account_for_write(db, account_id, user)
    p = AccountParty(account_id=account_id, **data.model_dump())
    _validate_party(account, p)
    db.add(p)
    db.commit()
    db.refresh(p)
    if p.is_pep:
        _recompute_pep(db, account)
    return p


def update_party(db: Session, party_id: int, data: AccountPartyUpdate, user: User) -> AccountParty:
    p = get_party(db, party_id)
    account = _get_account_for_write(db, p.account_id, user)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(p, field, value)
    try:
        _validate_party(account, p)
    except HTTPException:
        db.rollback()  # discard the in-memory edits
        raise
    db.commit()
    db.refresh(p)
    if "is_pep" in update_data:
        _recompute_pep(db, account)
    return p


def delete_party(db: Session, party_id: int, user: User) -> None:
    p = get_party(db, party_id)
    account = _get_account_for_write(db, p.account_id, user)
    was_pep = p.is_pep
    db.delete(p)
    db.commit()
    if was_pep:
        db.refresh(account)
        _recompute_pep(db, account)
