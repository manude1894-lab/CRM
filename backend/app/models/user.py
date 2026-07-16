"""SQLAlchemy model: User (with RBAC role)."""
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Reverse relationships
    cases_as_rm = relationship("Case", back_populates="rm", foreign_keys="Case.rm_id")
    cases_as_ops = relationship("Case", back_populates="ops_owner", foreign_keys="Case.ops_owner_id")
    accounts = relationship("Account", back_populates="owner", foreign_keys="Account.owner_id")
    activities = relationship("Activity", back_populates="owner", foreign_keys="Activity.owner_id")
    notifications = relationship("Notification", back_populates="user", foreign_keys="Notification.user_id")
