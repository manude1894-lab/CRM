"""DIFC client onboarding workflow: repurpose Opportunity->Case, add CDD/Compliance/Notification, drop Lead.

This is a destructive rewrite of the sales-pipeline schema (pre-production
demo data, re-seeded via `python -m app.seed --force` after migrating).

Revision ID: 0002_difc_onboarding_workflow
Revises: 0001_initial
Create Date: 2026-06-23 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision = "0002_difc_onboarding_workflow"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Demo data only — wipe rather than attempt a lossless enum/role migration.
    op.execute("TRUNCATE TABLE users, accounts RESTART IDENTITY CASCADE")

    op.drop_table("activities")
    op.drop_table("opportunities")
    op.drop_table("leads")

    for enum_name in ("deal_stage", "risk_level", "lead_status", "lead_source"):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)

    # ─── Accounts: rename cached stat columns ──────────────────────────────
    op.alter_column("accounts", "total_opportunities", new_column_name="total_cases")
    op.alter_column("accounts", "total_revenue_generated", new_column_name="total_invoiced_amount")

    # ─── Users: replace role enum (admin/sales_manager/sales_rep -> admin/rm/ops/screening) ──
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text")
    sa.Enum(name="user_role").drop(bind, checkfirst=True)
    new_user_role = sa.Enum("admin", "rm", "ops", "screening", name="user_role")
    new_user_role.create(bind, checkfirst=True)
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'rm'")

    # ─── New enums. create_type=False: created explicitly below, op.create_table()
    # must not also auto-create them (that double-create raises DuplicateObject).
    # Must be postgresql.ENUM specifically -- generic sa.Enum loses create_type when
    # SQLAlchemy adapts it to the dialect-specific impl during table-create DDL events.
    case_stage = PGEnum(
        "New Inquiry", "RM Assigned", "Docs Requested", "CDD/KYC In Review", "CDD Approved",
        "Invoice Raised", "Invoice Paid", "Ops Assigned", "Application Submitted",
        "License Received", "Active", name="case_stage", create_type=False,
    )
    case_status = PGEnum("Active", "Docs Pending", "Rejected", "On Hold", name="case_status", create_type=False)
    case_source = PGEnum("Senior Mgmt", "Social Media", "Referral", "Other", name="case_source", create_type=False)
    invoice_status = PGEnum("Not Raised", "Raised", "Paid", name="invoice_status", create_type=False)
    document_status = PGEnum("Not Started", "Submitted", "Under Review", "Approved", "Rejected", name="document_status", create_type=False)
    for e in (case_stage, case_status, case_source, invoice_status, document_status):
        e.create(bind, checkfirst=True)

    # ─── Cases ──────────────────────────────────────────────────────────────
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("case_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id")),
        sa.Column("rm_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("ops_owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("source", case_source, nullable=False, server_default="Other"),
        sa.Column("stage", case_stage, nullable=False, server_default="New Inquiry"),
        sa.Column("status", case_status, nullable=False, server_default="Active"),
        sa.Column("invoice_status", invoice_status, nullable=False, server_default="Not Raised"),
        sa.Column("invoice_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("invoice_raised_date", sa.Date),
        sa.Column("invoice_paid_date", sa.Date),
        sa.Column("license_received_date", sa.Date),
        sa.Column("license_expiry_date", sa.Date),
        sa.Column("tags", sa.String(500)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── CDD records + document checklist ──────────────────────────────────
    op.create_table(
        "cdd_records",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("cdd_form_status", document_status, nullable=False, server_default="Not Started"),
        sa.Column("kyc_verification_status", document_status, nullable=False, server_default="Not Started"),
        sa.Column("screening_reviewer_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "case_documents",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("cdd_record_id", sa.Integer, sa.ForeignKey("cdd_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_type", sa.String(150), nullable=False),
        sa.Column("received", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("received_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── Compliance schedule ────────────────────────────────────────────────
    op.create_table(
        "compliance_schedules",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("renewal_due_date", sa.Date),
        sa.Column("renewal_last_completed_date", sa.Date),
        sa.Column("renewal_cadence_months", sa.Integer, nullable=False, server_default="12"),
        sa.Column("compliance_filing_due_date", sa.Date),
        sa.Column("compliance_filing_last_completed_date", sa.Date),
        sa.Column("compliance_filing_cadence_months", sa.Integer, nullable=False, server_default="12"),
        sa.Column("tax_filing_due_date", sa.Date),
        sa.Column("tax_filing_last_completed_date", sa.Date),
        sa.Column("tax_filing_cadence_months", sa.Integer, nullable=False, server_default="12"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── Notifications ──────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id", ondelete="CASCADE")),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("link", sa.String(255)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── Activities (re-created, now linked to cases) ──────────────────────
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("activity_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("activity_date", sa.Date, nullable=False),
        sa.Column("activity_type", PGEnum(name="activity_type", create_type=False), nullable=False),
        sa.Column("status", PGEnum(name="activity_status", create_type=False), nullable=False, server_default="Planned"),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("outcome", sa.Text),
        sa.Column("next_action", sa.Text),
        sa.Column("due_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── Indexes ─────────────────────────────────────────────────────────────
    op.create_index("ix_cases_stage", "cases", ["stage"])
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_rm", "cases", ["rm_id"])
    op.create_index("ix_activities_case", "activities", ["case_id"])
    op.create_index("ix_activities_date", "activities", ["activity_date"])
    op.create_index("ix_notifications_user", "notifications", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("activities")
    op.drop_table("notifications")
    op.drop_table("compliance_schedules")
    op.drop_table("case_documents")
    op.drop_table("cdd_records")
    op.drop_table("cases")

    for enum_name in ("document_status", "invoice_status", "case_source", "case_status", "case_stage"):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)

    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(20) USING role::text")
    sa.Enum(name="user_role").drop(bind, checkfirst=True)
    old_user_role = sa.Enum("admin", "sales_manager", "sales_rep", name="user_role", create_type=False)
    old_user_role.create(bind, checkfirst=True)
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'sales_rep'")

    op.alter_column("accounts", "total_cases", new_column_name="total_opportunities")
    op.alter_column("accounts", "total_invoiced_amount", new_column_name="total_revenue_generated")

    lead_status = PGEnum("New", "Contacted", "Qualified", "Disqualified", "Converted", name="lead_status", create_type=False)
    lead_source = PGEnum("Conference", "LinkedIn", "Referral", "Website", "Partner", "Email", "Other", name="lead_source", create_type=False)
    priority_unused = PGEnum("Low", "Medium", "High", name="risk_level", create_type=False)
    deal_stage = PGEnum(
        "Lead Qualified", "Discovery Call", "Technical Discussion",
        "Proposal Shared", "Negotiation", "Pilot/POC",
        "Closed Won", "Closed Lost", name="deal_stage", create_type=False,
    )
    for e in (lead_status, lead_source, priority_unused, deal_stage):
        e.create(bind, checkfirst=True)

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("lead_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("company_name", sa.String(255), index=True, nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=False),
        sa.Column("designation", sa.String(255)),
        sa.Column("email", sa.String(255), index=True),
        sa.Column("phone", sa.String(50)),
        sa.Column("country", sa.String(100)),
        sa.Column("source", lead_source, nullable=False, server_default="Other"),
        sa.Column("industry", sa.String(100)),
        sa.Column("interest_area", sa.String(100)),
        sa.Column("lead_score", sa.Integer, nullable=False, server_default="50"),
        sa.Column("status", lead_status, nullable=False, server_default="New"),
        sa.Column("tags", sa.String(500)),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("notes", sa.Text),
        sa.Column("date_captured", sa.Date, nullable=False, server_default=sa.func.current_date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("opp_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("lead_id", sa.Integer, sa.ForeignKey("leads.id")),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id")),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("deal_name", sa.String(255), nullable=False),
        sa.Column("product_service", sa.String(100)),
        sa.Column("deal_type", sa.String(50)),
        sa.Column("stage", deal_stage, nullable=False, server_default="Lead Qualified"),
        sa.Column("probability", sa.Numeric(4, 2), nullable=False, server_default="0.10"),
        sa.Column("deal_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("weighted_revenue", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_close_date", sa.Date),
        sa.Column("proposal_sent_date", sa.Date),
        sa.Column("last_interaction_date", sa.Date),
        sa.Column("next_followup_date", sa.Date),
        sa.Column("decision_maker_identified", sa.String(10), nullable=False, server_default="No"),
        sa.Column("technical_validation", sa.String(50), nullable=False, server_default="Not Started"),
        sa.Column("risk_level", priority_unused, nullable=False, server_default="Medium"),
        sa.Column("competitor", sa.String(255)),
        sa.Column("stakeholders", sa.Text),
        sa.Column("tags", sa.String(500)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("activity_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("activity_date", sa.Date, nullable=False),
        sa.Column("activity_type", PGEnum(name="activity_type", create_type=False), nullable=False),
        sa.Column("status", PGEnum(name="activity_status", create_type=False), nullable=False, server_default="Planned"),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("outcome", sa.Text),
        sa.Column("next_action", sa.Text),
        sa.Column("due_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
