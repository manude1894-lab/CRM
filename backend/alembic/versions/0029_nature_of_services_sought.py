"""Add Account.nature_of_services_sought (client spec §23.13, Individual clients).

Revision ID: 0029_nature_of_services_sought
Revises: 0028_mobile_country_code_split
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_nature_of_services_sought"
down_revision = "0028_mobile_country_code_split"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("nature_of_services_sought", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("accounts", "nature_of_services_sought")
