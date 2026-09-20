"""Router: AccountParty (Shareholders/Directors/Authorised Signatories on a Client)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import AccountPartyCreate, AccountPartyRead, AccountPartyUpdate
from app.services import account_party_service

router = APIRouter(tags=["Client Parties"])


@router.get("/accounts/{account_id}/parties", response_model=List[AccountPartyRead])
def list_parties(account_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return account_party_service.list_parties(db, account_id)


@router.post("/accounts/{account_id}/parties", response_model=AccountPartyRead, status_code=status.HTTP_201_CREATED)
def create_party(account_id: int, data: AccountPartyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return account_party_service.create_party(db, account_id, data, user)


@router.patch("/account-parties/{party_id}", response_model=AccountPartyRead)
def update_party(party_id: int, data: AccountPartyUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return account_party_service.update_party(db, party_id, data, user)


@router.delete("/account-parties/{party_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_party(party_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    account_party_service.delete_party(db, party_id, user)
    return None
