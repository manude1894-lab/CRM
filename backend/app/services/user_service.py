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


def create_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    _check_business_role(db, data.business_role_id)
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
    security_service.password_set(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _check_business_role(db: Session, role_id) -> None:
    if role_id is not None and not db.get(Role, role_id):
        raise HTTPException(status_code=400, detail="Business role not found")


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    user = get_user(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    if "supervisor_id" in update_data:
        sup = update_data["supervisor_id"]
        if sup == user_id or access_control.would_create_supervisor_cycle(db, user_id, sup):
            raise HTTPException(status_code=400, detail="That supervisor reports to this user — the hierarchy would loop")
    if "business_role_id" in update_data:
        _check_business_role(db, update_data["business_role_id"])
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
