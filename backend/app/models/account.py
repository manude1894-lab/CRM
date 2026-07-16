"""SQLAlchemy model: Account (client company)."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Numeric, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class Priority(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_uid = Column(String(20), unique=True, index=True, nullable=False)  # ACC-0001

    company_name = Column(String(255), unique=True, nullable=False, index=True)
    industry = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    company_size = Column(String(100), nullable=True)
    website = Column(String(255), nullable=True)

    strategic_priority = Column(SAEnum(Priority, name="priority", values_callable=lambda obj: [e.value for e in obj]), default=Priority.MEDIUM, nullable=False)
    existing_relationship = Column(String(10), default="No", nullable=False)
    key_contacts = Column(Text, nullable=True)
    tags = Column(String(500), nullable=True)

    # Computed / denormalized
    total_cases = Column(Integer, default=0, nullable=False)
    total_invoiced_amount = Column(Numeric(14, 2), default=0, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="accounts", foreign_keys=[owner_id])
    cases = relationship("Case", back_populates="account")
