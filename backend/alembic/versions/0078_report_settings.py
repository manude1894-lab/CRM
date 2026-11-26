"""Report settings (Administrator) and favourite reports (each user) - Triam 26-11-2026.

Revision ID: 0078_report_settings
Revises: 0077_invoice_co_approval
Create Date: 2026-11-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0078_report_settings"
down_revision = "0077_invoice_co_approval"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_settings",
        sa.Column("report_key", sa.String(60), primary_key=True),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("role_ids", sa.JSON(), nullable=True),
        sa.Column("default_days", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "report_favourites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("report_key", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "report_key", name="uq_report_favourite"),
    )


def downgrade():
    op.drop_table("report_favourites")
    op.drop_table("report_settings")
