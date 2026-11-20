"""Invoice for Onboarding Services (Triam UAT 19-11-2026): the client's Yes / No answer, and on the invoice its
kind (Onboarding / Service Request), the amount payable to the Regn / Govt Authority and the introducer's
amount. Existing invoices for service requests are marked as such.

Revision ID: 0074_onboarding_invoice
Revises: 0073_report_export
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0074_onboarding_invoice"
down_revision = "0073_report_export"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("onboarding_invoice_wanted", sa.Boolean(), nullable=True))
    op.add_column("invoices", sa.Column("kind", sa.String(20), nullable=True))
    op.create_index("ix_invoices_kind", "invoices", ["kind"])
    op.add_column("invoices", sa.Column("govt_authority_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("invoices", sa.Column("govt_authority_currency", sa.String(3), nullable=True))
    op.add_column("invoices", sa.Column("introducer_involved", sa.Boolean(), nullable=True))
    op.add_column("invoices", sa.Column("introducer_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("invoices", sa.Column("introducer_currency", sa.String(3), nullable=True))
    op.execute("UPDATE invoices SET kind = 'Service Request' "
               "WHERE id IN (SELECT invoice_id FROM instructions WHERE invoice_id IS NOT NULL)")


def downgrade():
    for col in ("introducer_currency", "introducer_amount", "introducer_involved", "govt_authority_currency", "govt_authority_amount"):
        op.drop_column("invoices", col)
    op.drop_index("ix_invoices_kind", table_name="invoices")
    op.drop_column("invoices", "kind")
    op.drop_column("accounts", "onboarding_invoice_wanted")
