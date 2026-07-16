"""Users router (Admin-only CRUD)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.dependencies import require_admin, require_any
from app.schemas import UserCreate, UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=list[UserRead], summary="List users")
def list_users(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_any),  # any authenticated user can read the user list (needed for assignments)
):
    return user_service.list_users(db, skip, limit)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_any)):
    return user_service.get_user(db, user_id)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return user_service.create_user(db, data)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return user_service.update_user(db, user_id, data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    user_service.delete_user(db, user_id)
    return None
