"""SQLAlchemy model: Activity — a client's Visit Reports and Call Reports (BRD §15)."""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ActivityType(str, enum.Enum):
    VISIT_REPORT = "Visit Report"
    CALL_REPORT = "Call Report"


class ActivityStatus(str, enum.Enum):
    # Triam 23-11-2026 (S T Krishna): "Save Draft" keeps a report as Draft (still editable); "Save the Report"
    # makes it final (Completed): kept as written for later review, corrected only by adding a note.
    DRAFT = "Draft"
    PLANNED = "Planned"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    OVERDUE = "Overdue"


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    activity_uid = Column(String(20), unique=True, index=True, nullable=False)  # ACT-0001

    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    company_name = Column(String(255), nullable=False)
    activity_date = Column(Date, nullable=False)
    activity_type = Column(SAEnum(ActivityType, name="activity_type", values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    status = Column(SAEnum(ActivityStatus, name="activity_status", values_callable=lambda obj: [e.value for e in obj]), default=ActivityStatus.PLANNED, nullable=False)

    summary = Column(Text, nullable=False)
    outcome = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)

    # Visit / Call Report details
    client_contact = Column(String(150), nullable=True)  # who Triam met / spoke to
    attendees = Column(Text, nullable=True)  # Triam attendees
    location = Column(String(200), nullable=True)  # Visit Report
    purpose = Column(String(200), nullable=True)

    cancel_reason = Column(String(500), nullable=True)  # set when cancelled — records are never deleted
    finalised_at = Column(DateTime(timezone=True), nullable=True)  # "Save the Report"; locked from then on
    finalised_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account")
    owner = relationship("User", back_populates="activities", foreign_keys=[owner_id])
    finalised_by = relationship("User", foreign_keys=[finalised_by_id])
    corrections = relationship("ActivityCorrection", order_by="ActivityCorrection.id", cascade="all, delete-orphan",
                               back_populates="activity")


class ActivityCorrection(Base):
    """A note added to a final report (Triam 23-11-2026): the report's text stays as written; the note says what
    was wrong or missing, by whom and when."""
    __tablename__ = "activity_corrections"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    activity = relationship("Activity", back_populates="corrections")
    author = relationship("User")
