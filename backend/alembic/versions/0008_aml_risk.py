"""Add AML Risk Matrix: country_risk reference table + aml_risk_assessments.

Revision ID: 0008_aml_risk
Revises: 0007_invoices
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_aml_risk"
down_revision = "0007_invoices"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "country_risk",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kyc_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("default_to_high", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_country_risk_name", "country_risk", ["name"], unique=True)

    op.create_table(
        "aml_risk_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False, server_default="Entity"),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("director_id", sa.Integer(), sa.ForeignKey("directors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shareholder_id", sa.Integer(), sa.ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assessment_date", sa.Date(), nullable=True),
        sa.Column("completed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("matrix_version", sa.String(20), nullable=True),
        sa.Column("factors", sa.JSON(), nullable=True),
        sa.Column("total_weighted_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("calculated_rating", sa.String(20), nullable=True),
        sa.Column("override_reason", sa.String(500), nullable=True),
        sa.Column("onboarding_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("amended_rating", sa.String(20), nullable=True),
        sa.Column("mlro_notes", sa.Text(), nullable=True),
        sa.Column("mlro_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mlro_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_aml_risk_assessments_case_id", "aml_risk_assessments", ["case_id"])


def downgrade():
    op.drop_index("ix_aml_risk_assessments_case_id", table_name="aml_risk_assessments")
    op.drop_table("aml_risk_assessments")
    op.drop_index("ix_country_risk_name", table_name="country_risk")
    op.drop_table("country_risk")
