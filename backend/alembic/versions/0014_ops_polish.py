"""Tracker / ops polish.

- cases: introducer, onboarding_date
- instructions: cost_amount (paid to the registered agent)
- compliance_schedules: ar_filing_status, ar_reference_year
- new action_points table (shared WIP board)
- new pep_assessments table (standalone PEP / EDD assessment per party)

Revision ID: 0014_ops_polish
Revises: 0013_formation
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_ops_polish"
down_revision = "0013_formation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("introducer", sa.String(150), nullable=True))
    op.add_column("cases", sa.Column("onboarding_date", sa.Date(), nullable=True))

    op.add_column("instructions", sa.Column("cost_amount", sa.Numeric(12, 2), nullable=True))

    op.add_column("compliance_schedules", sa.Column("ar_filing_status", sa.String(30), nullable=False, server_default="Not Started"))
    op.add_column("compliance_schedules", sa.Column("ar_reference_year", sa.Integer(), nullable=True))

    op.create_table(
        "action_points",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Open"),
        sa.Column("priority", sa.String(10), nullable=False, server_default="Medium"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_action_points_case_id", "action_points", ["case_id"])

    op.create_table(
        "pep_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("director_id", sa.Integer(), sa.ForeignKey("directors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shareholder_id", sa.Integer(), sa.ForeignKey("shareholders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ubo_id", sa.Integer(), sa.ForeignKey("ubos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject_name", sa.String(255), nullable=False),
        sa.Column("pep_type", sa.String(40), nullable=True),
        sa.Column("position", sa.String(255), nullable=True),
        sa.Column("pep_jurisdiction", sa.String(120), nullable=True),
        sa.Column("since_date", sa.Date(), nullable=True),
        sa.Column("still_in_office", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("family_and_associates", sa.Text(), nullable=True),
        sa.Column("source_of_wealth_scrutiny", sa.Text(), nullable=True),
        sa.Column("source_of_funds_scrutiny", sa.Text(), nullable=True),
        sa.Column("edd_measures", sa.Text(), nullable=True),
        sa.Column("adverse_media_findings", sa.Text(), nullable=True),
        sa.Column("risk_conclusion", sa.String(30), nullable=True),
        sa.Column("senior_management_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assessed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assessment_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pep_assessments_case_id", "pep_assessments", ["case_id"])


def downgrade():
    op.drop_table("pep_assessments")
    op.drop_index("ix_action_points_case_id", table_name="action_points")
    op.drop_table("action_points")
    op.drop_column("compliance_schedules", "ar_reference_year")
    op.drop_column("compliance_schedules", "ar_filing_status")
    op.drop_column("instructions", "cost_amount")
    op.drop_column("cases", "onboarding_date")
    op.drop_column("cases", "introducer")
