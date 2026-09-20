"""Org structure — Departments master table + User department/title/supervisor (Phase D).

Revision ID: 0024_departments
Revises: 0023_account_individual_type
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0024_departments"
down_revision = "0023_account_individual_type"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("users", sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True))
    op.add_column("users", sa.Column("title", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))


def downgrade():
    op.drop_column("users", "supervisor_id")
    op.drop_column("users", "title")
    op.drop_column("users", "department_id")
    op.drop_table("departments")
