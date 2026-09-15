"""Add compliance/risk fields to accounts.

- accounts: registration_number, license_number, risk_rating, kyc_status

Revision ID: 0020_account_compliance_fields
Revises: 0019_new_requirements_batch
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_account_compliance_fields"
down_revision = "0019_new_requirements_batch"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("registration_number", sa.String(100), nullable=True))
    op.add_column("accounts", sa.Column("license_number", sa.String(100), nullable=True))
    op.add_column("accounts", sa.Column("risk_rating", sa.String(20), nullable=True))
    op.add_column("accounts", sa.Column("kyc_status", sa.String(30), nullable=False, server_default="Not Started"))


def downgrade():
    op.drop_column("accounts", "kyc_status")
    op.drop_column("accounts", "risk_rating")
    op.drop_column("accounts", "license_number")
    op.drop_column("accounts", "registration_number")
