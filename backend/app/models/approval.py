"""SQLAlchemy model: ApprovalRequest — one maker → checker review of a client (BRD §12 steps 11–13, §15).

A maker submits the client profile; an authorised checker (client.approve, not the maker) approves
or rejects it with a reason. Rows are the review history and are never deleted. `snapshot` keeps
the profile as submitted, so it's clear what the checker approved.

P3 — the same table is the Compliance inbox for every kind of review (request_type):
  client_profile    new client onboarding (P2)
  client_amendment  changes to an approved client; `payload` holds the staged edits, `changes` the
                    field-level before/after shown to the checker
  case_creation     a new case, waiting for Compliance before it can move through the pipeline
  case_amendment    changes to an approved case
"""
import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ApprovalStatus(str, enum.Enum):
    DRAFT = "Draft"  # amendment being prepared by the maker; not yet with Compliance
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    WITHDRAWN = "Withdrawn"
    DISCARDED = "Discarded"  # draft amendment abandoned by the maker


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    request_type = Column(String(30), nullable=False, default="client_profile")
    status = Column(String(20), nullable=False, default=ApprovalStatus.PENDING.value, index=True)

    maker_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    maker_comment = Column(Text, nullable=True)

    checker_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    reason_code = Column(String(60), nullable=True)  # rejection_reason master code
    reason_text = Column(Text, nullable=True)  # rejection explanation, or approval comment

    snapshot = Column(JSON, nullable=True)  # the record as it stood when submitted
    payload = Column(JSON, nullable=True)  # staged edits to apply on approval (amendments)
    changes = Column(JSON, nullable=True)  # before/after diff shown to the checker
    previous_request_id = Column(Integer, nullable=True)  # the rejected/withdrawn request this draft continues

    account = relationship("Account")
    case = relationship("Case")
    maker = relationship("User", foreign_keys=[maker_id])
    checker = relationship("User", foreign_keys=[checker_id])
