"""Add Account.incorporation_date (client spec §5.2).

Revision ID: 0027_account_incorporation_date
Revises: 0026_department_is_active
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0027_account_incorporation_date"
down_revision = "0026_department_is_active"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("incorporation_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("accounts", "incorporation_date")
