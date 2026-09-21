"""Split Contact Mobile into country code + number (client spec §15).

Adds new *_country_code / *_number column pairs to account_parties and
accounts; the old single-string mobile/individual_mobile columns are left
in place (unused going forward, not dropped) to avoid any data loss on a
live database.

Revision ID: 0028_mobile_country_code_split
Revises: 0027_account_incorporation_date
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0028_mobile_country_code_split"
down_revision = "0027_account_incorporation_date"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("account_parties", sa.Column("mobile_country_code", sa.String(6), nullable=True))
    op.add_column("account_parties", sa.Column("mobile_number", sa.String(12), nullable=True))
    op.add_column("accounts", sa.Column("individual_mobile_country_code", sa.String(6), nullable=True))
    op.add_column("accounts", sa.Column("individual_mobile_number", sa.String(12), nullable=True))


def downgrade():
    op.drop_column("accounts", "individual_mobile_number")
    op.drop_column("accounts", "individual_mobile_country_code")
    op.drop_column("account_parties", "mobile_number")
    op.drop_column("account_parties", "mobile_country_code")
