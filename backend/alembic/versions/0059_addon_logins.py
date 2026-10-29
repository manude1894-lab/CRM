"""Add-on logins instead of additional roles (Triam, 29-10-2026).

A person with more than one role has one login per role, each with its own email and password.
users.person_id links an add-on login to the person's main login. The old additional roles on a
single login (user_extra_roles) are removed: such a role is set up again as an add-on login.

Revision ID: 0059_addon_logins
Revises: 0058_biz_rationale_report
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op

revision = "0059_addon_logins"
down_revision = "0058_biz_rationale_report"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("person_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_users_person_id", "users", "users", ["person_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_users_person_id", "users", ["person_id"])
    op.drop_table("user_extra_roles")


def downgrade():
    op.create_table(
        "user_extra_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.drop_index("ix_users_person_id", table_name="users")
    op.drop_constraint("fk_users_person_id", "users", type_="foreignkey")
    op.drop_column("users", "person_id")
