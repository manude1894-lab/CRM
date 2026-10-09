"""SQLAlchemy model: Role — admin-managed business roles with permission flags (BRD §15, §18).

Business roles (CO, MLRO, RO, FO, Sales Manager, Dy MLRO, …) sit *on top of* the fixed system
tier in User.role (admin / rm / ops / screening). The tier still drives the existing screens;
a business role adds permissions. Code checks permissions via app.auth.permissions, never role names.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# Every permission flag the app understands, with an admin-facing description.
PERMISSIONS = {
    "client.approve": "Approve or reject client profiles and amendments (Checker)",
    "document.delete_submitted": "Delete documents after they have been submitted (Approver)",
    "master.manage": "Maintain master data lists",
    "audit.view": "View the full audit log",
    "view.all_clients": "See every client, regardless of RM",
    "view.department_clients": "See clients whose Anchor RM is in the same department",
    "client.final_approve": "Give the final approval to new clients after Compliance (Approver)",
    "client.cdd_edit": "Complete the CDD / risk assessment section of a client (Compliance)",
    "invoice.manage": "Raise invoices: invoice number, date, currency, amount and the invoice file (Accounts)",
    "prospect.assign": "Assign prospects to RMs (Prospecting Team Coordinator)",
}


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    permissions = Column(JSON, nullable=False, default=list)  # list[str], keys of PERMISSIONS
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    department = relationship("Department")
