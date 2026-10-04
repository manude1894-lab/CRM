"""Business roles router (BRD §15 / §18 Roles master, Admin-managed)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models import User, PERMISSIONS
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate, PermissionInfo
from app.services import role_service

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/permissions", response_model=list[PermissionInfo], summary="All permission flags")
def list_permissions(user: User = Depends(get_current_user)):
    return [PermissionInfo(key=k, description=v) for k, v in PERMISSIONS.items()]


@router.get("", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return role_service.list_roles(db)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(data: RoleCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return role_service.create_role(db, data)


@router.patch("/{role_id}", response_model=RoleRead)
def update_role(role_id: int, data: RoleUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return role_service.update_role(db, role_id, data)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    role_service.delete_role(db, role_id)
    return None
