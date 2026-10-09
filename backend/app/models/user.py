"""SQLAlchemy model: User (with RBAC role)."""
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


# A user can hold more than one business role (Triam BRD mark-up §13): the main role is
# users.business_role_id, any others are listed here. Permissions are the union of all of them.
user_extra_roles = Table(
    "user_extra_roles", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    RM = "rm"
    OPS = "ops"
    SCREENING = "screening"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole, name="user_role", values_callable=lambda obj: [e.value for e in obj]), default=UserRole.RM, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(100), nullable=True)
    mobile = Column(String(20), nullable=True)
    # P7 — login lockout and password tracking
    failed_login_count = Column(Integer, default=0, server_default="0", nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)  # this sign-in
    previous_login_at = Column(DateTime(timezone=True), nullable=True)  # shown as "last login" (Triam mark-up §2)  # for SMS notifications (BRD §17), e.g. +971501234567
    supervisor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # BRD §15 business role (CO / MLRO / RO / …) — adds permissions on top of the system tier in `role`.
    business_role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    business_role = relationship("Role", foreign_keys=[business_role_id])
    extra_roles = relationship("Role", secondary=user_extra_roles, lazy="selectin")

    @property
    def all_business_roles(self) -> list:
        """The main role first, then any additional ones (active roles only)."""
        roles = ([self.business_role] if self.business_role else []) + [r for r in self.extra_roles if r.id != self.business_role_id]
        return [r for r in roles if r.is_active]

    @property
    def extra_role_ids(self) -> list[int]:
        return [r.id for r in self.extra_roles]

    @property
    def permissions(self) -> list[str]:
        """Effective BRD §15 permission flags (exposed on /auth/me so the UI can show/hide actions)."""
        from app.auth.permissions import user_permissions  # local import: auth imports models
        return sorted(user_permissions(self))

    @property
    def business_role_name(self):
        """Shown as the user's role in the app (e.g. "MLRO") instead of the system tier."""
        names = [r.name for r in self.all_business_roles]
        return " · ".join(names) if names else None

    # Reverse relationships
    cases_as_rm = relationship("Case", back_populates="rm", foreign_keys="Case.rm_id")
    cases_as_ops = relationship("Case", back_populates="ops_owner", foreign_keys="Case.ops_owner_id")
    accounts = relationship("Account", back_populates="owner", foreign_keys="Account.owner_id")
    activities = relationship("Activity", back_populates="owner", foreign_keys="Activity.owner_id")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id")
