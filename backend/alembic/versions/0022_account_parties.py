"""Client-level Shareholders/Directors/Authorised Signatories (Phase B).

- new table account_parties (one discriminated table, party_role column)
- accounts: is_pep (server-computed rollup from account_parties)

Revision ID: 0022_account_parties
Revises: 0021_client_profile_core
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0022_account_parties"
down_revision = "0021_client_profile_core"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_parties",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("party_role", sa.String(30), nullable=False),
        sa.Column("constitution", sa.String(20), nullable=False, server_default="Individual"),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("dob_or_incorp_date", sa.Date(), nullable=True),
        sa.Column("id_or_license_expiry", sa.Date(), nullable=True),
        sa.Column("country_of_incorp_or_birth", sa.String(120), nullable=True),
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("country_of_residence", sa.String(120), nullable=True),
        sa.Column("residential_address", sa.JSON(), nullable=True),
        sa.Column("uae_visa_number", sa.String(50), nullable=True),
        sa.Column("uae_visa_expiry", sa.Date(), nullable=True),
        sa.Column("is_pep", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("effective_ownership_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("nominee_director_name", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column("accounts", sa.Column("is_pep", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("accounts", "is_pep")
    op.drop_table("account_parties")
