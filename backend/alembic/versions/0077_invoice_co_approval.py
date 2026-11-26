"""Onboarding invoice requests for clients not yet approved go to the CO first (Triam UAT 25-11-2026 row 182).

Revision ID: 0077_invoice_co_approval
Revises: 0076_report_draft_final
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0077_invoice_co_approval"
down_revision = "0076_report_draft_final"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("co_decided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("invoices", sa.Column("co_decided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("co_decision", sa.String(20), nullable=True))
    op.add_column("invoices", sa.Column("co_comment", sa.String(500), nullable=True))


def downgrade():
    for c in ("co_comment", "co_decision", "co_decided_at", "co_decided_by_id"):
        op.drop_column("invoices", c)
