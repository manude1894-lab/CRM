"""SQLAlchemy model: User (with RBAC role)."""
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    """System tier: Administrator, or a staff user whose access comes from business roles (BRD §13)."""
    ADMIN = "admin"
    RM = "rm"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole, name="user_role", values_callable=lambda obj: [e.value for e in obj]), default=UserRole.RM, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # Ezee Tech support account: hidden from other users, changeable only by itself, may delete users.
    is_super_admin = Column(Boolean, default=False, server_default="false", nullable=False)

    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(100), nullable=True)
    mobile = Column(String(20), nullable=True)  # for SMS notifications, e.g. +971501234567
    # login lockout and password tracking
    failed_login_count = Column(Integer, default=0, server_default="0", nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)  # this sign-in
    previous_login_at = Column(DateTime(timezone=True), nullable=True)  # shown as "last login" (BRD §2)
    supervisor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # BRD §15 business role (CO / MLRO / RO / …) — adds permissions on top of the system tier in `role`.
    business_role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    # A person with more than one role has one login per role, each with its own email and password
    # (Triam, 29-10-2026). Add-on logins point to the person's main login; the main login has none.
    person_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    business_role = relationship("Role", foreign_keys=[business_role_id])
    main_login = relationship("User", remote_side=[id], foreign_keys=[person_id], back_populates="addon_logins")
    addon_logins = relationship("User", foreign_keys=[person_id], back_populates="main_login")

    @property
    def all_business_roles(self) -> list:
        """The login's role (one per login), if active."""
        return [self.business_role] if self.business_role and self.business_role.is_active else []

    @property
    def person_key(self) -> int:
        """Same value for every login of one person: the main login's id."""
        return self.person_id or self.id

    @property
    def linked_logins(self) -> list[dict]:
        """The person's other active logins, main login first (shown at the top to switch to)."""
        main = self.main_login if self.person_id else self
        logins = [main] + [u for u in sorted(main.addon_logins, key=lambda u: u.id)]
        return [{"id": u.id, "email": u.email, "role_name": u.business_role_name or ("Administrator" if u.role == UserRole.ADMIN else None),
                 "is_main": u.person_id is None}
                for u in logins if u.id != self.id and u.is_active]

    @property
    def permissions(self) -> list[str]:
        """Effective BRD §15 permission flags (exposed on /auth/me so the UI can show/hide actions)."""
        from app.auth.permissions import user_permissions  # local import: auth imports models
        return sorted(user_permissions(self))

    @property
    def handles_clients(self) -> bool:
        """True for client-facing staff (RM, RO, FO, Sales Manager …): no business role, or at least one
        that carries none of the central-desk permissions. Decides the menu a user gets."""
        from app.auth.permissions import CENTRAL_PERMISSIONS  # local import: auth imports models
        roles = self.all_business_roles
        return not roles or any(not (set(r.permissions or []) & CENTRAL_PERMISSIONS) for r in roles)

    @property
    def business_role_name(self):
        """Shown as the user's role in the app (e.g. "MLRO") instead of the system tier."""
        names = [r.name for r in self.all_business_roles]
        return " · ".join(names) if names else None

    # Reverse relationships
    accounts = relationship("Account", back_populates="owner", foreign_keys="Account.owner_id")
    activities = relationship("Activity", back_populates="owner", foreign_keys="Activity.owner_id")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id")
