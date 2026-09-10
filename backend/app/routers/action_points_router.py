"""Action Points router — the shared WIP task board."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models import User
from app.schemas import ActionPointCreate, ActionPointUpdate, ActionPointRead
from app.services import action_point_service

router = APIRouter(prefix="/action-points", tags=["Action Points"])


@router.get("", response_model=List[ActionPointRead])
def list_action_points(status: Optional[str] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return action_point_service.list_action_points(db, user, status)


@router.post("", response_model=ActionPointRead, status_code=status.HTTP_201_CREATED)
def create_action_point(data: ActionPointCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return action_point_service.create_action_point(db, data, user)


@router.patch("/{ap_id}", response_model=ActionPointRead)
def update_action_point(ap_id: int, data: ActionPointUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return action_point_service.update_action_point(db, ap_id, data, user)


@router.delete("/{ap_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action_point(ap_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    action_point_service.delete_action_point(db, ap_id, user)
    return None
