"""SQLAlchemy model: ApprovalRequest — one maker → checker review of a client (BRD §12 steps 11–13, §15).

A maker submits the client profile; an authorised checker (client.approve, not the maker) approves
or rejects it with a reason. Rows are the review history and are never deleted. `snapshot` keeps
the profile as submitted, so it's clear what the checker approved. P3 adds request_type "amendment".
"""
import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ApprovalStatus(str, enum.Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(30), nullable=False, default="client_profile")
    status = Column(String(20), nullable=False, default=ApprovalStatus.PENDING.value, index=True)

    maker_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    maker_comment = Column(Text, nullable=True)

    checker_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    reason_code = Column(String(60), nullable=True)  # rejection_reason master code
    reason_text = Column(Text, nullable=True)  # rejection explanation, or approval comment

    snapshot = Column(JSON, nullable=True)  # the profile + parties as submitted

    account = relationship("Account")
    maker = relationship("User", foreign_keys=[maker_id])
    checker = relationship("User", foreign_keys=[checker_id])
