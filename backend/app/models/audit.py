"""SQLAlchemy model: AuditLog — append-only record of material CRM activity (BRD §13, §15).

Written automatically by app.audit (a before_flush listener) for creates/updates/deletes on
audited models, and explicitly for events like login. There is no update/delete API: rows are
never changed once written.

`account_id` is denormalised onto each row so a client's full history (its own fields, its
parties, its documents) can be read with one indexed query.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    action = Column(String(30), nullable=False)  # create / update / delete / login / login_failed / …
    subject_type = Column(String(60), nullable=False)  # model class name, e.g. "Account"
    subject_id = Column(Integer, nullable=True)
    account_id = Column(Integer, nullable=True, index=True)  # owning client, when there is one

    changes = Column(JSON, nullable=True)  # {field: [old, new]}
    summary = Column(String(500), nullable=True)
    ip_address = Column(String(64), nullable=True)

    user = relationship("User")
