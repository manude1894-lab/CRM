"""Triam BRD mark-up §2: show the user's last login date / time at the next login.

users.last_login_at is this sign-in; users.previous_login_at the one before it (shown to the user).

Revision ID: 0049_login_times
Revises: 0048_invoice_module
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0049_login_times"
down_revision = "0048_invoice_module"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("previous_login_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "previous_login_at")
    op.drop_column("users", "last_login_at")
