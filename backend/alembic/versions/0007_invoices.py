"""Add invoices ledger table and link instructions to it.

Revision ID: 0007_invoices
Revises: 0006_party_documents
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_invoices"
down_revision = "0006_party_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_number", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Draft"),
        sa.Column("raised_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invoices_case_id", "invoices", ["case_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.add_column("instructions", sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_instructions_invoice_id", "instructions", ["invoice_id"])


def downgrade():
    op.drop_index("ix_instructions_invoice_id", table_name="instructions")
    op.drop_column("instructions", "invoice_id")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_case_id", table_name="invoices")
    op.drop_table("invoices")
