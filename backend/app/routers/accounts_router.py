"""Accounts router."""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user, require_admin
from app.models import User
from app.schemas import AccountCreate, AccountRead, AccountUpdate
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("", summary="List accounts")
def list_accounts(
    skip: int = 0, limit: int = 100,
    search: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    priority: Optional[str] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = account_service.list_accounts(
        db, user, skip, limit, search, industry, country, priority,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [AccountRead.model_validate(i) for i in items], "total": total}


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return account_service.get_account(db, account_id, user)


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return account_service.create_account(db, data, user)


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int, data: AccountUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return account_service.update_account(db, account_id, data, user)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    account_service.delete_account(db, account_id, user)
    return None
