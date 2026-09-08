"""Formation detail + calendar-anchored compliance.

- new company_profiles table (formation / statutory detail, 1:1 with cases)
- compliance_schedules: rename compliance_filing_* -> esr_filing_*, tax_filing_* -> ar_filing_*,
  add bo_filing_due_date / bo_filing_last_completed_date

Revision ID: 0010_formation_compliance
Revises: 0009_ubo_register
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_formation_compliance"
down_revision = "0009_ubo_register"
branch_labels = None
depends_on = None

_RENAMES = [
    ("compliance_filing_due_date", "esr_filing_due_date"),
    ("compliance_filing_last_completed_date", "esr_filing_last_completed_date"),
    ("compliance_filing_cadence_months", "esr_filing_cadence_months"),
    ("tax_filing_due_date", "ar_filing_due_date"),
    ("tax_filing_last_completed_date", "ar_filing_last_completed_date"),
    ("tax_filing_cadence_months", "ar_filing_cadence_months"),
]


def upgrade():
    op.create_table(
        "company_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("chinese_name", sa.String(255), nullable=True),
        sa.Column("company_number", sa.String(100), nullable=True),
        sa.Column("registered_agent", sa.String(50), nullable=True),
        sa.Column("incorporation_date", sa.Date(), nullable=True),
        sa.Column("proposed_name_1", sa.String(255), nullable=True),
        sa.Column("proposed_name_2", sa.String(255), nullable=True),
        sa.Column("proposed_name_3", sa.String(255), nullable=True),
        sa.Column("name_check_status", sa.String(30), nullable=False, server_default="Not Submitted"),
        sa.Column("name_confirmed_date", sa.Date(), nullable=True),
        sa.Column("authorised_shares", sa.Integer(), nullable=True),
        sa.Column("par_value", sa.Numeric(12, 4), nullable=True),
        sa.Column("share_currency", sa.String(10), nullable=True, server_default="USD"),
        sa.Column("no_par_value", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_of_funds", sa.String(50), nullable=True),
        sa.Column("source_of_funds_description", sa.Text(), nullable=True),
        sa.Column("nature_of_business", sa.String(60), nullable=True),
        sa.Column("business_description", sa.Text(), nullable=True),
        sa.Column("company_secretary", sa.String(40), nullable=True),
        sa.Column("es_financial_year_end", sa.String(5), nullable=True),
        sa.Column("accounting_financial_year_end", sa.String(5), nullable=True),
        sa.Column("act_certificate_of_incorporation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("act_memorandum_articles", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("act_register_of_members", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("act_register_of_directors_stamped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("act_company_stamp", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activation_docs_received_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    for old, new in _RENAMES:
        op.alter_column("compliance_schedules", old, new_column_name=new)

    op.add_column("compliance_schedules", sa.Column("bo_filing_due_date", sa.Date(), nullable=True))
    op.add_column("compliance_schedules", sa.Column("bo_filing_last_completed_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("compliance_schedules", "bo_filing_last_completed_date")
    op.drop_column("compliance_schedules", "bo_filing_due_date")
    for old, new in _RENAMES:
        op.alter_column("compliance_schedules", new, new_column_name=old)
    op.drop_table("company_profiles")
