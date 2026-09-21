"""Add Account.country_of_birth (client spec §23.3, Individual clients).

Revision ID: 0025_account_country_of_birth
Revises: 0024_departments
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0025_account_country_of_birth"
down_revision = "0024_departments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("country_of_birth", sa.String(120), nullable=True))


def downgrade():
    op.drop_column("accounts", "country_of_birth")
