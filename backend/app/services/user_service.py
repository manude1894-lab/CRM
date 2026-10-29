"""Service layer: User management (Admin-only)."""
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import User, UserRole, Role
from app.schemas.user import UserCreate, UserUpdate
from app.auth.security import hash_password
from app.services import access_control


def _hidden_from(viewer) -> bool:
    """The super admin account is invisible to everyone but itself."""
    return not (viewer is not None and viewer.is_super_admin)


def list_users(db: Session, skip: int = 0, limit: int = 100, viewer: User | None = None) -> list[User]:
    q = db.query(User)
    if _hidden_from(viewer):
        q = q.filter(User.is_super_admin == False)  # noqa: E712
    return q.order_by(User.id).offset(skip).limit(limit).all()


def get_user(db: Session, user_id: int, viewer: User | None = None) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user or (user.is_super_admin and _hidden_from(viewer) and (viewer is None or viewer.id != user.id)):
        raise HTTPException(status_code=404, detail="User not found")
    return user


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def find_by_email(db: Session, email: str) -> User | None:
    """Emails match whatever the capitals: "Kalyan@AskTriam.com" signs in as kalyan@asktriam.com
    (phones capitalise the first letter). Also finds addresses stored with capitals before."""
    return db.query(User).filter(func.lower(User.email) == normalize_email(email)).first()


def _assert_company_email(email: str) -> None:
    """BRD §13 — when USER_EMAIL_DOMAINS is set (e.g. "asktriam.com"), users must have a
    company email address; access lasts while that address is active."""
    from app.config import settings
    domains = [d.strip().lower() for d in (settings.USER_EMAIL_DOMAINS or "").split(",") if d.strip()]
    if domains and email.rsplit("@", 1)[-1].lower() not in domains:
        raise HTTPException(status_code=400, detail=f"Use a company email address ({', '.join('@' + d for d in domains)})")


def create_user(db: Session, data: UserCreate) -> User:
    data.email = normalize_email(data.email)
    _assert_company_email(data.email)
    if find_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    _check_business_role(db, data.business_role_id)
    main = _main_login(db, data.person_id)
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
        person_id=main.id if main else None,
    )
    security_service.password_set(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _check_business_role(db: Session, role_id) -> None:
    if role_id is not None and not db.get(Role, role_id):
        raise HTTPException(status_code=400, detail="Business role not found")


def _main_login(db: Session, person_id) -> User | None:
    """An add-on login belongs to a person's main login (one login per role, Triam 29-10-2026)."""
    if person_id is None:
        return None
    main = db.get(User, person_id)
    if main is None or main.is_super_admin:
        raise HTTPException(status_code=400, detail="User not found")
    if main.person_id is not None:
        raise HTTPException(status_code=400, detail="Add the login to the person's main login, not to another add-on login")
    if not main.is_active:
        raise HTTPException(status_code=400, detail="That person's main login is inactive")
    return main


def update_user(db: Session, user_id: int, data: UserUpdate, viewer: User | None = None) -> User:
    user = get_user(db, user_id, viewer)
    update_data = data.model_dump(exclude_unset=True)
    if user.is_super_admin:
        if viewer is None or viewer.id != user.id:
            raise HTTPException(status_code=404, detail="User not found")
        if update_data.get("is_active") is False or update_data.get("role", UserRole.ADMIN) != UserRole.ADMIN:
            raise HTTPException(status_code=400, detail="The support account can't be deactivated or given another user type")
    losing_admin = user.role == UserRole.ADMIN and user.is_active and not user.is_super_admin and (
        update_data.get("is_active") is False or update_data.get("role", UserRole.ADMIN) != UserRole.ADMIN)
    active_admins = db.query(User).filter(User.role == UserRole.ADMIN, User.is_active == True,  # noqa: E712
                                          User.is_super_admin == False).count()  # noqa: E712
    if losing_admin and active_admins <= 1:
        raise HTTPException(status_code=400, detail="This is the only active administrator. Add another administrator first.")
    if "supervisor_id" in update_data:
        sup = update_data["supervisor_id"]
        if sup == user_id or access_control.would_create_supervisor_cycle(db, user_id, sup):
            raise HTTPException(status_code=400, detail="That supervisor reports to this user, so the reporting line would go round in a circle")
    if "business_role_id" in update_data:
        _check_business_role(db, update_data["business_role_id"])
    if update_data.get("email"):
        update_data["email"] = normalize_email(update_data["email"])
    if update_data.get("email") and update_data["email"] != normalize_email(user.email):
        _assert_company_email(update_data["email"])
        other = find_by_email(db, update_data["email"])
        if other and other.id != user.id:
            raise HTTPException(status_code=400, detail="Email already registered")
    if "password" in update_data:
        from app.services import security_service
        new_password = update_data.pop("password")
        security_service.assert_password_ok(new_password, user.email)
        user.hashed_password = hash_password(new_password)
        security_service.password_set(user)  # an admin reset also unlocks the account
    for field, value in update_data.items():
        setattr(user, field, value)
    # Deactivating a person's main login deactivates all their logins.
    if update_data.get("is_active") is False and user.person_id is None:
        for addon in user.addon_logins:
            addon.is_active = False
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int, viewer: User) -> None:
    """Super admin only: remove a user login for good (e.g. a test or mistaken account). A user who still
    owns clients or activities must have them reassigned first; their other history is kept
    without the name."""
    from app.models import Account, Activity
    if not viewer.is_super_admin:
        raise HTTPException(status_code=403, detail="Only the support account can delete users")
    user = get_user(db, user_id, viewer)
    if user.id == viewer.id:
        raise HTTPException(status_code=400, detail="The support account can't delete itself")
    owned = (db.query(Account).filter((Account.owner_id == user.id) | (Account.spoc_id == user.id)).count()
             + db.query(Activity).filter(Activity.owner_id == user.id).count())
    if owned:
        raise HTTPException(status_code=409, detail=f"{user.name} still owns {owned} client(s) or activities. "
                                                    "Reassign them first, or deactivate the user instead.")
    db.delete(user)
    db.commit()
