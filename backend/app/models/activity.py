"""SQLAlchemy model: Activity (meetings, calls, demos, emails)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ActivityType(str, enum.Enum):
    CALL = "Call"
    EMAIL = "Email"
    MEETING = "Meeting"
    DEMO = "Demo"
    FOLLOW_UP = "Follow-up"
    NOTE = "Note"


class ActivityStatus(str, enum.Enum):
    PLANNED = "Planned"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    OVERDUE = "Overdue"


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    activity_uid = Column(String(20), unique=True, index=True, nullable=False)  # ACT-0001

    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    company_name = Column(String(255), nullable=False)
    activity_date = Column(Date, nullable=False)
    activity_type = Column(SAEnum(ActivityType, name="activity_type", values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    status = Column(SAEnum(ActivityStatus, name="activity_status", values_callable=lambda obj: [e.value for e in obj]), default=ActivityStatus.PLANNED, nullable=False)

    summary = Column(Text, nullable=False)
    outcome = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="activities")
    owner = relationship("User", back_populates="activities", foreign_keys=[owner_id])
