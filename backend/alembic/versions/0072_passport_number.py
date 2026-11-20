"""Passport Number on the individual client and on each person of a client (Triam 20-11-2026). Required at
Submit, with a passport copy, for an individual client and every individual person; records saved before
are asked for it the next time they are submitted.

Revision ID: 0072_passport_number
Revises: 0071_onboarding_statuses
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0072_passport_number"
down_revision = "0071_onboarding_statuses"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("passport_number", sa.String(20), nullable=True))
    op.add_column("account_parties", sa.Column("passport_number", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("account_parties", "passport_number")
    op.drop_column("accounts", "passport_number")
