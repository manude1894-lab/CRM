"""Master data router (BRD §18). Any signed-in user reads active items; maintaining them needs
the `master.manage` permission (Admins have it)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.auth.permissions import has_permission
from app.database import get_db
from app.models import User, MASTER_LIST_TYPES
from app.schemas.master import MasterItemCreate, MasterItemRead, MasterItemUpdate, MasterListType
from app.services import master_service

router = APIRouter(prefix="/masters", tags=["Master Data"])


@router.get("", response_model=list[MasterListType], summary="Available master lists")
def list_types(user: User = Depends(get_current_user)):
    return [MasterListType(list_type=k, title=v) for k, v in MASTER_LIST_TYPES.items()]


@router.get("/{list_type}", response_model=list[MasterItemRead])
def list_items(list_type: str, include_inactive: bool = False,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Inactive items are only for maintainers; everyone else gets the selectable values.
    show_inactive = include_inactive and has_permission(user, "master.manage")
    return master_service.list_items(db, list_type, include_inactive=show_inactive)


@router.post("/{list_type}", response_model=MasterItemRead, status_code=status.HTTP_201_CREATED)
def create_item(list_type: str, data: MasterItemCreate,
                db: Session = Depends(get_db), user: User = Depends(require_permission("master.manage"))):
    return master_service.create_item(db, list_type, data)


@router.patch("/items/{item_id}", response_model=MasterItemRead)
def update_item(item_id: int, data: MasterItemUpdate,
                db: Session = Depends(get_db), user: User = Depends(require_permission("master.manage"))):
    return master_service.update_item(db, item_id, data)
