"""Onboarding statuses the RM sets: Pending with Client, Pending with Regn Authority, On Hold, Dropped
(Triam UAT 18-11-2026). profile_status is a String(30), so the new values need no change; the reason for
the current status is kept on the client.

Revision ID: 0071_onboarding_statuses
Revises: 0070_minor_guardian
Create Date: 2026-11-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0071_onboarding_statuses"
down_revision = "0070_minor_guardian"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("status_reason_code", sa.String(40), nullable=True))
    op.add_column("accounts", sa.Column("status_reason", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("accounts", "status_reason")
    op.drop_column("accounts", "status_reason_code")
