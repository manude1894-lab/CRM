"""Service layer: AccountParty (Shareholders/Directors/Authorised Signatories on a Client)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Account, AccountParty, User
from app.schemas.account_party import AccountPartyCreate, AccountPartyUpdate
from app.services import account_service


def _get_account_for_write(db: Session, account_id: int, user: User) -> Account:
    # Reuses account_service.get_account — same 404 + RM-ownership check, no duplication.
    return account_service.get_account(db, account_id, user)


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
