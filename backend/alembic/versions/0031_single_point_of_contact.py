"""Add Account.single_point_of_contact (client CRM-change-request item 6).

Revision ID: 0031_single_point_of_contact
Revises: 0030_document_account_scope
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_single_point_of_contact"
down_revision = "0030_document_account_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("single_point_of_contact", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("accounts", "single_point_of_contact")
