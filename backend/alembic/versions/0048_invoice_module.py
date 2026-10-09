"""Triam BRD mark-up §16 — Invoice module.

The RM / Sales requests an invoice for a client onboarding or a service request (the "instruction to
the Accounts Department") and attaches the pricing approvals; Accounts records the Invoice No, Date,
Currency and Amount, attaches the invoice file, and marks it paid.

- invoices: belongs to a client (account_id); the case is optional; currency; who requested it and
  when; who raised it.
- documents.invoice_id: pricing approvals and invoice files attached to an invoice.

Revision ID: 0048_invoice_module
Revises: 0047_document_categories_links
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0048_invoice_module"
down_revision = "0047_document_categories_links"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("invoices", "case_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("invoices", sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_invoices_account_id", "invoices", ["account_id"])
    op.add_column("invoices", sa.Column("currency", sa.String(3), nullable=False, server_default="AED"))
    op.add_column("invoices", sa.Column("requested_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("invoices", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("invoices", sa.Column("raised_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.execute("UPDATE invoices SET account_id = (SELECT account_id FROM cases WHERE cases.id = invoices.case_id) WHERE account_id IS NULL")
    op.add_column("documents", sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_documents_invoice_id", "documents", ["invoice_id"])


def downgrade():
    op.drop_index("ix_documents_invoice_id", "documents")
    op.drop_column("documents", "invoice_id")
    for col in ("raised_by_id", "requested_at", "requested_by_id", "currency"):
        op.drop_column("invoices", col)
    op.drop_index("ix_invoices_account_id", "invoices")
    op.drop_column("invoices", "account_id")
    op.alter_column("invoices", "case_id", existing_type=sa.Integer(), nullable=False)
