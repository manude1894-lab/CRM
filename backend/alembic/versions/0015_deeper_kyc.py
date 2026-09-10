"""Deeper KYC form capture.

- directors / shareholders: Appendix A individual fields + entity_details JSON
- shareholders: nominator block, charges JSON
- company_profiles: nature-of-business sub-fields

No new tables.

Revision ID: 0015_deeper_kyc
Revises: 0014_ops_polish
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_deeper_kyc"
down_revision = "0014_ops_polish"
branch_labels = None
depends_on = None

_APPENDIX_A = [
    ("email", sa.String(255)),
    ("mobile", sa.String(50)),
    ("occupation", sa.String(150)),
    ("employer_name", sa.String(255)),
    ("tax_residency_country", sa.String(100)),
    ("tax_id_number", sa.String(60)),
    ("source_of_funds", sa.String(255)),
    ("source_of_wealth", sa.Text()),
    ("pep_notes", sa.Text()),
]


def upgrade():
    for table in ("directors", "shareholders"):
        for name, coltype in _APPENDIX_A:
            op.add_column(table, sa.Column(name, coltype, nullable=True))
        op.add_column(table, sa.Column("is_pep", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column("entity_details", sa.JSON(), nullable=True))

    op.add_column("shareholders", sa.Column("nominator_name", sa.String(255), nullable=True))
    op.add_column("shareholders", sa.Column("nominator_address", sa.String(255), nullable=True))
    op.add_column("shareholders", sa.Column("nominator_relationship", sa.String(150), nullable=True))
    op.add_column("shareholders", sa.Column("nominee_agreement_date", sa.Date(), nullable=True))
    op.add_column("shareholders", sa.Column("charges", sa.JSON(), nullable=True))

    op.add_column("company_profiles", sa.Column("business_countries", sa.Text(), nullable=True))
    op.add_column("company_profiles", sa.Column("key_counterparties", sa.Text(), nullable=True))
    op.add_column("company_profiles", sa.Column("asset_types", sa.Text(), nullable=True))
    op.add_column("company_profiles", sa.Column("expected_annual_turnover", sa.String(60), nullable=True))
    op.add_column("company_profiles", sa.Column("expected_active_transactions", sa.String(60), nullable=True))


def downgrade():
    for col in ("expected_active_transactions", "expected_annual_turnover", "asset_types",
                "key_counterparties", "business_countries"):
        op.drop_column("company_profiles", col)

    for col in ("charges", "nominee_agreement_date", "nominator_relationship",
                "nominator_address", "nominator_name"):
        op.drop_column("shareholders", col)

    for table in ("shareholders", "directors"):
        op.drop_column(table, "entity_details")
        op.drop_column(table, "is_pep")
        for name, _ in _APPENDIX_A:
            op.drop_column(table, name)
