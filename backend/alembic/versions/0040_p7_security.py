"""P7 hardening: login lockout and password-change tracking.

users.failed_login_count / users.locked_until — an account is locked for a short time after
repeated wrong passwords. users.password_changed_at — set whenever the user (or an admin) sets a
new password.

Revision ID: 0040_p7_security
Revises: 0039_p6_engagements
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0040_p7_security"
down_revision = "0039_p6_engagements"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
