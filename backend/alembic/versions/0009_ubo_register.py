"""Add UBO register: ubos table + ubo_id on case_documents and aml_risk_assessments.

Revision ID: 0009_ubo_register
Revises: 0008_aml_risk
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_ubo_register"
down_revision = "0008_aml_risk"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ubos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(150), nullable=True),
        sa.Column("middle_name", sa.String(150), nullable=True),
        sa.Column("last_name", sa.String(150), nullable=True),
        sa.Column("former_name", sa.String(255), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("place_of_birth", sa.String(150), nullable=True),
        sa.Column("nationality", sa.String(120), nullable=True),
        sa.Column("country_of_residence", sa.String(120), nullable=True),
        sa.Column("passport_number", sa.String(50), nullable=True),
        sa.Column("passport_expiry", sa.Date(), nullable=True),
        sa.Column("national_id", sa.String(50), nullable=True),
        sa.Column("residential_address", sa.String(255), nullable=True),
        sa.Column("residential_city", sa.String(100), nullable=True),
        sa.Column("residential_country", sa.String(100), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("percentage_interest", sa.Numeric(5, 2), nullable=True),
        sa.Column("ownership_nature", sa.String(20), nullable=False, server_default="Direct"),
        sa.Column("nature_of_control", sa.String(255), nullable=True),
        sa.Column("held_via_shareholder_id", sa.Integer(), sa.ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_pep", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pep_notes", sa.Text(), nullable=True),
        sa.Column("employer_name", sa.String(255), nullable=True),
        sa.Column("job_title", sa.String(150), nullable=True),
        sa.Column("sector", sa.String(150), nullable=True),
        sa.Column("years_employed", sa.String(50), nullable=True),
        sa.Column("source_of_wealth_category", sa.String(50), nullable=True),
        sa.Column("source_of_wealth_details", sa.Text(), nullable=True),
        sa.Column("appointment_date", sa.Date(), nullable=True),
        sa.Column("cessation_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ubos_case_id", "ubos", ["case_id"])

    op.add_column("case_documents", sa.Column("ubo_id", sa.Integer(), sa.ForeignKey("ubos.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_case_documents_ubo_id", "case_documents", ["ubo_id"])

    op.add_column("aml_risk_assessments", sa.Column("ubo_id", sa.Integer(), sa.ForeignKey("ubos.id", ondelete="SET NULL"), nullable=True))


def downgrade():
    op.drop_column("aml_risk_assessments", "ubo_id")
    op.drop_index("ix_case_documents_ubo_id", table_name="case_documents")
    op.drop_column("case_documents", "ubo_id")
    op.drop_index("ix_ubos_case_id", table_name="ubos")
    op.drop_table("ubos")
