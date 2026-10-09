"""Triam BRD mark-up §5, §5.1–5.3, §6: profile fields.

accounts: New Client Category (Under Formation / Existing), company contact mobile + email, Detailed
Nature of Business / Profession, LEI and its expiry, "Is this one-time service".
account_parties: Nationality (mandatory for every party); "Joint Holder" is a new party role for
Individual clients (no column needed).

Revision ID: 0046_markup_profile_fields
Revises: 0045_prospect_first
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0046_markup_profile_fields"
down_revision = "0045_prospect_first"
branch_labels = None
depends_on = None

ACCOUNT_COLUMNS = [
    ("client_category", sa.String(20)),
    ("contact_mobile_country_code", sa.String(6)),
    ("contact_mobile_number", sa.String(12)),
    ("contact_email", sa.String(255)),
    ("nature_of_business", sa.Text()),
    ("lei_number", sa.String(20)),
    ("lei_expiry_date", sa.Date()),
    ("is_one_time_service", sa.Boolean()),
]


def upgrade():
    for name, type_ in ACCOUNT_COLUMNS:
        op.add_column("accounts", sa.Column(name, type_, nullable=True))
    op.add_column("account_parties", sa.Column("nationality", sa.String(120), nullable=True))


def downgrade():
    op.drop_column("account_parties", "nationality")
    for name, _ in reversed(ACCOUNT_COLUMNS):
        op.drop_column("accounts", name)
