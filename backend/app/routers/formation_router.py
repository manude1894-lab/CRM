"""Formation router — screening / MLRO sign-off / Vistra loop / §V milestones (1:1 with Case)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import FormationRecordRead, FormationRecordUpdate
from app.services import formation_service

router = APIRouter(tags=["Formation"])


@router.get("/cases/{case_id}/formation", response_model=FormationRecordRead)
def get_formation(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return formation_service.get_or_create(db, case_id)


@router.patch("/cases/{case_id}/formation", response_model=FormationRecordRead)
def update_formation(case_id: int, data: FormationRecordUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return formation_service.update(db, case_id, data, user)
