"""Individual client type on Account (Phase C).

- accounts: account_type (Corporate / Individual)
- accounts: Individual Details fields (DOB, passport, nationality, occupation,
  source of funds/wealth, residence, residential address, UAE visa)

Revision ID: 0023_account_individual_type
Revises: 0022_account_parties
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0023_account_individual_type"
down_revision = "0022_account_parties"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("account_type", sa.String(20), nullable=False, server_default="Corporate"))

    op.add_column("accounts", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("accounts", sa.Column("nationality", sa.String(120), nullable=True))
    op.add_column("accounts", sa.Column("passport_number", sa.String(50), nullable=True))
    op.add_column("accounts", sa.Column("passport_expiry_date", sa.Date(), nullable=True))
    op.add_column("accounts", sa.Column("occupation", sa.String(150), nullable=True))
    op.add_column("accounts", sa.Column("source_of_funds", sa.String(255), nullable=True))
    op.add_column("accounts", sa.Column("source_of_wealth", sa.String(255), nullable=True))
    op.add_column("accounts", sa.Column("country_of_residence", sa.String(120), nullable=True))
    op.add_column("accounts", sa.Column("residential_address", sa.JSON(), nullable=True))
    op.add_column("accounts", sa.Column("individual_mobile", sa.String(50), nullable=True))
    op.add_column("accounts", sa.Column("individual_email", sa.String(255), nullable=True))
    op.add_column("accounts", sa.Column("uae_visa_number", sa.String(50), nullable=True))
    op.add_column("accounts", sa.Column("uae_visa_expiry", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("accounts", "uae_visa_expiry")
    op.drop_column("accounts", "uae_visa_number")
    op.drop_column("accounts", "individual_email")
    op.drop_column("accounts", "individual_mobile")
    op.drop_column("accounts", "residential_address")
    op.drop_column("accounts", "country_of_residence")
    op.drop_column("accounts", "source_of_wealth")
    op.drop_column("accounts", "source_of_funds")
    op.drop_column("accounts", "occupation")
    op.drop_column("accounts", "passport_expiry_date")
    op.drop_column("accounts", "passport_number")
    op.drop_column("accounts", "nationality")
    op.drop_column("accounts", "date_of_birth")
    op.drop_column("accounts", "account_type")
