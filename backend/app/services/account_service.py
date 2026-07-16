"""Service layer: Account business logic."""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from typing import Optional

from app.models import Account, User, UserRole
from app.schemas.account import AccountCreate, AccountUpdate
from app.utils.uid import next_uid


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


def get_account(db: Session, account_id: int, user: User) -> Account:
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if user.role == UserRole.RM and acc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return acc


def create_account(db: Session, data: AccountCreate, user: User) -> Account:
    existing = db.query(Account).filter(Account.company_name == data.company_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Account with this company name already exists")

    owner_id = data.owner_id or user.id
    payload = data.model_dump(exclude={"owner_id"})
    acc = Account(
        account_uid=next_uid(db, Account, "account_uid", "ACC"),
        **payload,
        owner_id=owner_id,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def update_account(db: Session, account_id: int, data: AccountUpdate, user: User) -> Account:
    acc = get_account(db, account_id, user)
    update_data = data.model_dump(exclude_unset=True)
    if user.role == UserRole.RM:
        update_data.pop("owner_id", None)
    for field, value in update_data.items():
        setattr(acc, field, value)
    db.commit()
    db.refresh(acc)
    return acc


def delete_account(db: Session, account_id: int, user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only Admin can delete accounts")
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
