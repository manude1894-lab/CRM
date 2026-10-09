"""Service layer: User management (Admin-only)."""
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import User, UserRole, Role
from app.schemas.user import UserCreate, UserUpdate
from app.auth.security import hash_password
from app.services import access_control


def list_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return db.query(User).order_by(User.id).offset(skip).limit(limit).all()


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _assert_company_email(email: str) -> None:
    """Triam mark-up §13 — when USER_EMAIL_DOMAINS is set (e.g. "asktriam.com"), users must have a
    company email address; access lasts while that address is active."""
    from app.config import settings
    domains = [d.strip().lower() for d in (settings.USER_EMAIL_DOMAINS or "").split(",") if d.strip()]
    if domains and email.rsplit("@", 1)[-1].lower() not in domains:
        raise HTTPException(status_code=400, detail=f"Use a company email address ({', '.join('@' + d for d in domains)})")


def create_user(db: Session, data: UserCreate) -> User:
    _assert_company_email(data.email)
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    _check_business_role(db, data.business_role_id)
    extra = _extra_roles(db, data.extra_role_ids)
    from app.services import security_service
    security_service.assert_password_ok(data.password, data.email)
    user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        role=data.role,
        is_active=data.is_active,
        department_id=data.department_id,
        title=data.title,
        supervisor_id=data.supervisor_id,
        business_role_id=data.business_role_id,
        mobile=data.mobile,
    )
    user.extra_roles = extra
    security_service.password_set(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _check_business_role(db: Session, role_id) -> None:
    if role_id is not None and not db.get(Role, role_id):
        raise HTTPException(status_code=400, detail="Business role not found")


def _extra_roles(db: Session, role_ids) -> list[Role]:
    """Additional business roles — one person may hold several (e.g. MLRO and Approver)."""
    if not role_ids:
        return []
    roles = db.query(Role).filter(Role.id.in_(set(role_ids))).all()
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=400, detail="Business role not found")
    return roles


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    if "supervisor_id" in update_data:
        sup = update_data["supervisor_id"]
        if sup == user_id or access_control.would_create_supervisor_cycle(db, user_id, sup):
            raise HTTPException(status_code=400, detail="That supervisor reports to this user — the hierarchy would loop")
    if "business_role_id" in update_data:
        _check_business_role(db, update_data["business_role_id"])
    if update_data.get("email") and update_data["email"] != user.email:
        _assert_company_email(update_data["email"])
    if "extra_role_ids" in update_data:
        user.extra_roles = _extra_roles(db, update_data.pop("extra_role_ids"))
    if "password" in update_data:
        from app.services import security_service
        new_password = update_data.pop("password")
        security_service.assert_password_ok(new_password, user.email)
        user.hashed_password = hash_password(new_password)
        security_service.password_set(user)  # an admin reset also unlocks the account
    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = get_user(db, user_id)
    if user.role == UserRole.ADMIN:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    db.delete(user)
    db.commit()
