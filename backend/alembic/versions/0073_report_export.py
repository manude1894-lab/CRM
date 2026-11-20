"""Who may download reports as Excel / PDF: a tick-box on each user, set by the Administrator (Triam UAT
19-11-2026). Off for everyone; Administrators may always.

Revision ID: 0073_report_export
Revises: 0072_passport_number
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0073_report_export"
down_revision = "0072_passport_number"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("can_export_reports", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("users", "can_export_reports")
