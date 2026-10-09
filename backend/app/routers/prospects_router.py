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
from app.schemas.prospect import DuplicateMatch, ProspectAssignRequest
from app.services import prospect_service

router = APIRouter(prefix="/prospects", tags=["Prospects"])


def _read(p) -> ProspectRead:
    out = ProspectRead.model_validate(p)
    out.owner_name = p.owner.name if p.owner else None
    out.assigned_by_name = p.assigned_by.name if p.assigned_by else None
    return out


@router.get("", response_model=List[ProspectRead])
def list_prospects(status: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [_read(p) for p in prospect_service.list_prospects(db, user, status)]


@router.get("/check-duplicate", response_model=List[DuplicateMatch], summary="Fuzzy-match an in-progress name against existing prospects and clients")
def check_duplicate_prospect(name: str, exclude_id: Optional[int] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.find_similar(db, name, exclude_id)


@router.get("/{prospect_id}", response_model=ProspectRead)
def get_prospect(prospect_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _read(prospect_service.get_prospect(db, prospect_id, user))


@router.post("", response_model=ProspectRead, status_code=status.HTTP_201_CREATED)
def create_prospect(data: ProspectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _read(prospect_service.create_prospect(db, data, user))


@router.patch("/{prospect_id}", response_model=ProspectRead)
def update_prospect(prospect_id: int, data: ProspectUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _read(prospect_service.update_prospect(db, prospect_id, data, user))


@router.post("/{prospect_id}/assign", response_model=ProspectRead, summary="Assign the prospect to an RM (Triam mark-up §4A)")
def assign_prospect(prospect_id: int, data: ProspectAssignRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _read(prospect_service.assign_prospect(db, prospect_id, data.rm_id, data.comments, user))


@router.delete("/{prospect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prospect(prospect_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    prospect_service.delete_prospect(db, prospect_id, user)
    return None


@router.post("/{prospect_id}/convert", response_model=CaseRead, summary="Convert a Won prospect into an onboarding Case")
def convert_prospect(prospect_id: int, data: ProspectConvertRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return prospect_service.convert_to_case(db, prospect_id, data, user)
