"""Add Department.is_active (client spec §VI — Departments table with active/inactive status).

Revision ID: 0026_department_is_active
Revises: 0025_account_country_of_birth
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0026_department_is_active"
down_revision = "0025_account_country_of_birth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("departments", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    op.drop_column("departments", "is_active")
