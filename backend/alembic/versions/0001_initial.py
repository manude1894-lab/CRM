"""Initial schema: users, leads, accounts, opportunities, activities

Revision ID: 0001_initial
Revises:
Create Date: 2025-04-20 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums. create_type=False on each: we create them explicitly via the loop below
    # (checkfirst=True), so op.create_table() below must not try to auto-create them
    # again as part of column DDL (that double-create is what raises DuplicateObject).
    # Must be postgresql.ENUM specifically -- generic sa.Enum loses create_type when
    # SQLAlchemy adapts it to the dialect-specific impl during table-create DDL events.
    user_role = PGEnum("admin", "sales_manager", "sales_rep", name="user_role", create_type=False)
    lead_status = PGEnum("New", "Contacted", "Qualified", "Disqualified", "Converted", name="lead_status", create_type=False)
    lead_source = PGEnum("Conference", "LinkedIn", "Referral", "Website", "Partner", "Email", "Other", name="lead_source", create_type=False)
    priority = PGEnum("High", "Medium", "Low", name="priority", create_type=False)
    deal_stage = PGEnum(
        "Lead Qualified", "Discovery Call", "Technical Discussion",
        "Proposal Shared", "Negotiation", "Pilot/POC",
        "Closed Won", "Closed Lost", name="deal_stage", create_type=False,
    )
    risk_level = PGEnum("Low", "Medium", "High", name="risk_level", create_type=False)
    activity_type = PGEnum("Call", "Email", "Meeting", "Demo", "Follow-up", "Note", name="activity_type", create_type=False)
    activity_status = PGEnum("Planned", "Completed", "Cancelled", "Overdue", name="activity_status", create_type=False)

    bind = op.get_bind()
    for e in (user_role, lead_status, lead_source, priority, deal_stage, risk_level, activity_type, activity_status):
        e.create(bind, checkfirst=True)

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="sales_rep"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Accounts
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("account_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("company_name", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("industry", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("company_size", sa.String(100)),
        sa.Column("website", sa.String(255)),
        sa.Column("strategic_priority", priority, nullable=False, server_default="Medium"),
        sa.Column("existing_relationship", sa.String(10), nullable=False, server_default="No"),
        sa.Column("key_contacts", sa.Text),
        sa.Column("tags", sa.String(500)),
        sa.Column("total_opportunities", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_revenue_generated", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Leads
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

    # Opportunities
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
        sa.Column("risk_level", risk_level, nullable=False, server_default="Medium"),
        sa.Column("competitor", sa.String(255)),
        sa.Column("stakeholders", sa.Text),
        sa.Column("tags", sa.String(500)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Activities
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("activity_uid", sa.String(20), unique=True, index=True, nullable=False),
        sa.Column("opportunity_id", sa.Integer, sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("activity_date", sa.Date, nullable=False),
        sa.Column("activity_type", activity_type, nullable=False),
        sa.Column("status", activity_status, nullable=False, server_default="Planned"),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("outcome", sa.Text),
        sa.Column("next_action", sa.Text),
        sa.Column("due_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Indexes for common queries
    op.create_index("ix_opps_stage", "opportunities", ["stage"])
    op.create_index("ix_opps_owner", "opportunities", ["owner_id"])
    op.create_index("ix_opps_close_date", "opportunities", ["expected_close_date"])
    op.create_index("ix_activities_opp", "activities", ["opportunity_id"])
    op.create_index("ix_activities_date", "activities", ["activity_date"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_source", "leads", ["source"])


def downgrade() -> None:
    for table in ("activities", "opportunities", "leads", "accounts", "users"):
        op.drop_table(table)
    bind = op.get_bind()
    for enum_name in (
        "activity_status", "activity_type", "risk_level", "deal_stage",
        "priority", "lead_source", "lead_status", "user_role",
    ):
        sa.Enum(name=enum_name).drop(bind, checkfirst=True)
