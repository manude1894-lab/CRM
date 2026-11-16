"""A minor Shareholder / UBO or Beneficiary is onboarded through a parent or guardian (Triam 16-11-2026).

TRN / VAT and Corp Tax numbers now take letters, up to 20 characters; their String(30) columns need no change.

Revision ID: 0070_minor_guardian
Revises: 0069_one_time_services
Create Date: 2026-11-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0070_minor_guardian"
down_revision = "0069_one_time_services"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("account_parties", sa.Column("guardian_name", sa.String(255), nullable=True))
    op.add_column("account_parties", sa.Column("guardian_relationship", sa.String(60), nullable=True))


def downgrade():
    op.drop_column("account_parties", "guardian_relationship")
    op.drop_column("account_parties", "guardian_name")
