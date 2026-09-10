"""SQLAlchemy model: ActionPoint — the Instruction Tracker's "Action Points - WIP" sheet.

A shared, informal list of open operational tasks, not tied to the Case pipeline.
Optionally linked to an entity. Every authenticated user sees the whole board.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ActionPointStatus(str, enum.Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class ActionPoint(Base):
    __tablename__ = "action_points"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    detail = Column(Text, nullable=True)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status = Column(String(20), default=ActionPointStatus.OPEN.value, nullable=False)
    priority = Column(String(10), default="Medium", nullable=False)  # High / Medium / Low

    due_date = Column(Date, nullable=True)
    completed_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case")
    owner = relationship("User", foreign_keys=[owner_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
