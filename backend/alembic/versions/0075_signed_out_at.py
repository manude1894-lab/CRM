"""Signing out ends the login's sessions on the server (review 22-11-2026): the time of the last sign-out.

Revision ID: 0075_signed_out_at
Revises: 0074_onboarding_invoice
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0075_signed_out_at"
down_revision = "0074_onboarding_invoice"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("signed_out_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "signed_out_at")
