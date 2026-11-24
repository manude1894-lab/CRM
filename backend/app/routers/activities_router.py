"""Activities router."""
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import ActivityCreate, ActivityRead, ActivityUpdate
from app.schemas.activity import CorrectionCreate
from app.schemas.common import CancelRequest
from app.services import activity_service

router = APIRouter(prefix="/activities", tags=["Activities"])


@router.get("", summary="List activities")
def list_activities(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
    account_id: Optional[int] = None,
    activity_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    status: Optional[str] = Query(None, description="Draft | Final | Cancelled"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = activity_service.list_activities(
        db, user, skip, limit, activity_type, owner_id, search, account_id=account_id, status=status,
        date_from=date_from, date_to=date_to,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [ActivityRead.model_validate(i) for i in items], "total": total}


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return activity_service.get_activity(db, activity_id, user)


@router.post("", response_model=ActivityRead, status_code=201)
def create_activity(data: ActivityCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return activity_service.create_activity(db, data, user)


@router.patch("/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: int, data: ActivityUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return activity_service.update_activity(db, activity_id, data, user)


@router.post("/{activity_id}/cancel", status_code=204,
             summary="Cancel with a reason (records are never deleted)")
def cancel_activity(activity_id: int, data: CancelRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    activity_service.cancel_activity(db, activity_id, data.reason, user)
    return None


@router.post("/{activity_id}/corrections", response_model=ActivityRead,
             summary="Add a correction note to a final report (the report stays as written)")
def add_correction(activity_id: int, data: CorrectionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return activity_service.add_correction(db, activity_id, data.text, user)
