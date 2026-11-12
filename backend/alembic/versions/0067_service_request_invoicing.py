"""Service request invoicing fields (Triam's Invoice Box template, 11-11-2026).

The RM records the charge with its currency, what the client has paid and when, and any service
provider involved; Submit sends the request to the Accountant (submitted_at / submitted_by_id).

Revision ID: 0067_service_request_invoicing
Revises: 0066_master_code_lengths
Create Date: 2026-11-12
"""
import sqlalchemy as sa
from alembic import op

revision = "0067_service_request_invoicing"
down_revision = "0066_master_code_lengths"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("instructions", sa.Column("charge_currency", sa.String(3), nullable=False, server_default="AED"))
    op.add_column("instructions", sa.Column("amount_paid", sa.Numeric(12, 2), nullable=True))
    op.add_column("instructions", sa.Column("amount_paid_currency", sa.String(3), nullable=True))
    op.add_column("instructions", sa.Column("payment_received_date", sa.Date(), nullable=True))
    op.add_column("instructions", sa.Column("service_provider_involved", sa.Boolean(), nullable=True))
    op.add_column("instructions", sa.Column("service_provider_name", sa.String(150), nullable=True))
    op.add_column("instructions", sa.Column("service_provider_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("instructions", sa.Column("service_provider_currency", sa.String(3), nullable=True))
    op.add_column("instructions", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("instructions", sa.Column("submitted_by_id", sa.Integer(),
                                            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    # Requests already invoiced (the old "Completed with a charge" path) count as submitted.
    op.execute("UPDATE instructions SET submitted_at = updated_at WHERE invoice_id IS NOT NULL")


def downgrade():
    for col in ("submitted_by_id", "submitted_at", "service_provider_currency", "service_provider_amount",
                "service_provider_name", "service_provider_involved", "payment_received_date",
                "amount_paid_currency", "amount_paid", "charge_currency"):
        op.drop_column("instructions", col)
