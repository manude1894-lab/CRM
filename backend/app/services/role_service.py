"""Service layer: business roles (BRD §15 / §18 Roles master)."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Role, User, PERMISSIONS
from app.schemas.role import RoleCreate, RoleUpdate


def _clean_permissions(perms) -> list[str]:
    unknown = [p for p in perms or [] if p not in PERMISSIONS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown permission(s): {', '.join(unknown)}")
    return sorted(set(perms or []))


def list_roles(db: Session) -> list[Role]:
    return db.query(Role).order_by(Role.name).all()


def get_role(db: Session, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def create_role(db: Session, data: RoleCreate) -> Role:
    if db.query(Role).filter(Role.name == data.name).first():
        raise HTTPException(status_code=400, detail="A role with this name already exists")
    payload = data.model_dump()
    payload["permissions"] = _clean_permissions(payload.get("permissions"))
    role = Role(**payload)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, role_id: int, data: RoleUpdate) -> Role:
    role = get_role(db, role_id)
    update = data.model_dump(exclude_unset=True)
    if "permissions" in update:
        update["permissions"] = _clean_permissions(update["permissions"])
    if "name" in update and update["name"] != role.name and db.query(Role).filter(Role.name == update["name"]).first():
        raise HTTPException(status_code=400, detail="A role with this name already exists")
    for field, value in update.items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: int) -> None:
    role = get_role(db, role_id)
    in_use = db.query(User).filter(User.business_role_id == role_id).count()
    if in_use:
        raise HTTPException(status_code=400, detail=f"Role is assigned to {in_use} user(s) — deactivate it instead")
    db.delete(role)
    db.commit()
