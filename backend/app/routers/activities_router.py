"""Activities router."""
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import ActivityCreate, ActivityRead, ActivityUpdate
from app.services import activity_service

router = APIRouter(prefix="/activities", tags=["Activities"])


@router.get("", summary="List activities")
def list_activities(
    skip: int = 0, limit: int = 100,
    case_id: Optional[int] = None,
    activity_type: Optional[str] = None,
    owner_id: Optional[int] = None,
    search: Optional[str] = None,
    response: Response = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = activity_service.list_activities(
        db, user, skip, limit, case_id, activity_type, owner_id, search,
    )
    if response is not None:
        response.headers["X-Total-Count"] = str(total)
    return {"items": [ActivityRead.model_validate(i) for i in items], "total": total}


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return activity_service.get_activity(db, activity_id, user)


@router.post("", response_model=ActivityRead, status_code=status.HTTP_201_CREATED)
def create_activity(data: ActivityCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return activity_service.create_activity(db, data, user)


@router.patch("/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: int, data: ActivityUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return activity_service.update_activity(db, activity_id, data, user)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    activity_service.delete_activity(db, activity_id, user)
    return None
