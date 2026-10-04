"""SQLAlchemy model: MasterItem — admin-managed lists of values (BRD §18 Master Data).

One generic table instead of one per list: every BRD master (Triam entities, services, tags,
regulators, licensing authorities, document categories, rejection reasons) has the same shape —
a stored code, a display label, an order and an active flag. `code` is what records store;
for most lists it equals the label (so existing free-text data keeps working), document
categories use short codes because the BRD labels exceed the 40-char column.

Items are deactivated, never deleted, so historical records still resolve their labels.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


# The list types the app knows about. Adding a new list = add it here + seed it in a migration.
MASTER_LIST_TYPES = {
    "triam_entity": "Triam Entities",
    "service": "Services",
    "tag": "Client Tags",
    "regulator": "Regulators",
    "licensing_authority": "Licensing Authorities",
    "document_category": "Document Categories",
    "rejection_reason": "Rejection Reasons",
}


class MasterItem(Base):
    __tablename__ = "master_items"
    __table_args__ = (UniqueConstraint("list_type", "code", name="uq_master_items_type_code"),)

    id = Column(Integer, primary_key=True, index=True)
    list_type = Column(String(40), nullable=False, index=True)
    code = Column(String(60), nullable=False)
    label = Column(String(150), nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    meta = Column(JSON, nullable=True)  # list-specific extras, e.g. {"opens_free_text": true} for "Other"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
