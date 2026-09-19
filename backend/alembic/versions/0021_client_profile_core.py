"""Client profile core fields (Phase A of client-database spec).

- accounts: licensing/regulatory block, registered/operating address (JSON),
  TRN/VAT + corp tax, financial_year_end, introducer, services_obtained (JSON),
  profile_status, engagement letter fields, AML classification + review date.

Revision ID: 0021_client_profile_core
Revises: 0020_account_compliance_fields
Create Date: 2026-09-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_client_profile_core"
down_revision = "0020_account_compliance_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("licensing_authority", sa.String(150), nullable=True))
    op.add_column("accounts", sa.Column("license_start_date", sa.Date(), nullable=True))
    op.add_column("accounts", sa.Column("license_expiry_date", sa.Date(), nullable=True))
    op.add_column("accounts", sa.Column("is_regulated", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("accounts", sa.Column("regulator_name", sa.String(50), nullable=True))
    op.add_column("accounts", sa.Column("regulator_other", sa.String(100), nullable=True))
    op.add_column("accounts", sa.Column("license_category", sa.String(100), nullable=True))
    op.add_column("accounts", sa.Column("license_activities", sa.Text(), nullable=True))

    op.add_column("accounts", sa.Column("registered_address", sa.JSON(), nullable=True))
    op.add_column("accounts", sa.Column("operating_address", sa.JSON(), nullable=True))

    op.add_column("accounts", sa.Column("trn_vat_number", sa.String(30), nullable=True))
    op.add_column("accounts", sa.Column("corp_tax_registered", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("accounts", sa.Column("corp_tax_registration_number", sa.String(30), nullable=True))

    op.add_column("accounts", sa.Column("financial_year_end", sa.String(5), nullable=True))

    op.add_column("accounts", sa.Column("has_introducer", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("accounts", sa.Column("introducer_name", sa.String(255), nullable=True))

    op.add_column("accounts", sa.Column("services_obtained", sa.JSON(), nullable=True))

    op.add_column("accounts", sa.Column("profile_status", sa.String(30), nullable=False, server_default="New"))

    op.add_column("accounts", sa.Column("engagement_letter_signed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("accounts", sa.Column("engagement_letter_valid_until", sa.Date(), nullable=True))

    op.add_column("accounts", sa.Column("aml_classification", sa.String(20), nullable=True))
    op.add_column("accounts", sa.Column("edd_reason", sa.String(255), nullable=True))
    op.add_column("accounts", sa.Column("cdd_completion_date", sa.Date(), nullable=True))
    op.add_column("accounts", sa.Column("next_aml_review_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("accounts", "next_aml_review_date")
    op.drop_column("accounts", "cdd_completion_date")
    op.drop_column("accounts", "edd_reason")
    op.drop_column("accounts", "aml_classification")
    op.drop_column("accounts", "engagement_letter_valid_until")
    op.drop_column("accounts", "engagement_letter_signed")
    op.drop_column("accounts", "profile_status")
    op.drop_column("accounts", "services_obtained")
    op.drop_column("accounts", "introducer_name")
    op.drop_column("accounts", "has_introducer")
    op.drop_column("accounts", "financial_year_end")
    op.drop_column("accounts", "corp_tax_registration_number")
    op.drop_column("accounts", "corp_tax_registered")
    op.drop_column("accounts", "trn_vat_number")
    op.drop_column("accounts", "operating_address")
    op.drop_column("accounts", "registered_address")
    op.drop_column("accounts", "license_activities")
    op.drop_column("accounts", "license_category")
    op.drop_column("accounts", "regulator_other")
    op.drop_column("accounts", "regulator_name")
    op.drop_column("accounts", "is_regulated")
    op.drop_column("accounts", "license_expiry_date")
    op.drop_column("accounts", "license_start_date")
    op.drop_column("accounts", "licensing_authority")
