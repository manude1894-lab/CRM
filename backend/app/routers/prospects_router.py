"""Prospects router — pre-Case proposal tracking."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import (
    ProspectCreate, ProspectUpdate, ProspectRead, ProspectConvertRequest, CaseRead,
)
from app.services import prospect_service

router = APIRouter(prefix="/prospects", tags=["Prospects"])


@router.get("", response_model=List[ProspectRead])
def list_prospects(status: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.list_prospects(db, user, status)


@router.get("/{prospect_id}", response_model=ProspectRead)
def get_prospect(prospect_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.get_prospect(db, prospect_id, user)


@router.post("", response_model=ProspectRead, status_code=status.HTTP_201_CREATED)
def create_prospect(data: ProspectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.create_prospect(db, data, user)


@router.patch("/{prospect_id}", response_model=ProspectRead)
def update_prospect(prospect_id: int, data: ProspectUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.update_prospect(db, prospect_id, data, user)


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prospect(prospect_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    prospect_service.delete_prospect(db, prospect_id, user)
    return None


@router.post("/{prospect_id}/convert", response_model=CaseRead, summary="Convert a Won prospect into an onboarding Case")
def convert_prospect(prospect_id: int, data: ProspectConvertRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.convert_to_case(db, prospect_id, data, user)
