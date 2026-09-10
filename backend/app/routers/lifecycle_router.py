"""Entity lifecycle router — closure / strike-off / restoration / RA transfer (1:1 with Case)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import EntityLifecycleRead, EntityLifecycleUpdate
from app.services import lifecycle_service

router = APIRouter(tags=["Entity Lifecycle"])


@router.get("/cases/{case_id}/lifecycle", response_model=EntityLifecycleRead)
def get_lifecycle(case_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return lifecycle_service.get_or_create(db, case_id)


@router.patch("/cases/{case_id}/lifecycle", response_model=EntityLifecycleRead)
def update_lifecycle(case_id: int, data: EntityLifecycleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return lifecycle_service.update(db, case_id, data, user)
