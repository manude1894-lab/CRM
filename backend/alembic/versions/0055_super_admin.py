"""Super admin: the Ezee Tech support account. Hidden from every other user, changeable only by
itself, and the only account allowed to delete user logins.

Revision ID: 0055_super_admin
Revises: 0054_other_free_text
Create Date: 2026-10-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0055_super_admin"
down_revision = "0054_other_free_text"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_super_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE users SET is_super_admin = true WHERE lower(email) = 'admin@ezeetechgroup.com'")


def downgrade():
    op.drop_column("users", "is_super_admin")
