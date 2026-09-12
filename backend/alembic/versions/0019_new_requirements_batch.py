"""New requirements batch — ADGM/DIFC, CDD exception, multi-RM/SPOC, Prospects,
service catalog + auto-invoicing, Engagement Letter + feedback.

- company_profiles: entity_category, regulator
- cdd_records: exception_granted / exception_reason / exception_granted_by_id /
  exception_granted_at / exception_expires_on
- accounts: spoc_id
- cases: engagement_letter_sent_date, engagement_letter_signed_date
- new tables: case_relationship_managers, prospects, service_subscriptions,
  service_feedback

Revision ID: 0019_new_requirements_batch
Revises: 0018_document_form_gaps
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_new_requirements_batch"
down_revision = "0018_document_form_gaps"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_profiles", sa.Column("entity_category", sa.String(60), nullable=True))
    op.add_column("company_profiles", sa.Column("regulator", sa.String(60), nullable=True))

    op.add_column("cdd_records", sa.Column("exception_granted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("cdd_records", sa.Column("exception_reason", sa.Text(), nullable=True))
    op.add_column("cdd_records", sa.Column("exception_granted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("cdd_records", sa.Column("exception_granted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cdd_records", sa.Column("exception_expires_on", sa.Date(), nullable=True))

    op.add_column("accounts", sa.Column("spoc_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    op.add_column("cases", sa.Column("engagement_letter_sent_date", sa.Date(), nullable=True))
    op.add_column("cases", sa.Column("engagement_letter_signed_date", sa.Date(), nullable=True))

    op.create_table(
        "case_relationship_managers",
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "prospects",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("prospect_uid", sa.String(20), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(150), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="New"),
        sa.Column("proposal_sent_date", sa.Date(), nullable=True),
        sa.Column("proposal_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("next_follow_up_date", sa.Date(), nullable=True),
        sa.Column("lost_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("converted_case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "service_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(150), nullable=False),
        sa.Column("billing_frequency", sa.String(20), nullable=False, server_default="Monthly"),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="Active"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("next_billing_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_service_subscriptions_case_id", "service_subscriptions", ["case_id"])

    op.create_table(
        "service_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instruction_id", sa.Integer(), sa.ForeignKey("instructions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("received_via", sa.String(20), nullable=True),
        sa.Column("recorded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("feedback_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_service_feedback_case_id", "service_feedback", ["case_id"])


def downgrade():
    op.drop_index("ix_service_feedback_case_id", table_name="service_feedback")
    op.drop_table("service_feedback")
    op.drop_index("ix_service_subscriptions_case_id", table_name="service_subscriptions")
    op.drop_table("service_subscriptions")
    op.drop_table("prospects")
    op.drop_table("case_relationship_managers")
    op.drop_column("cases", "engagement_letter_signed_date")
    op.drop_column("cases", "engagement_letter_sent_date")
    op.drop_column("accounts", "spoc_id")
    op.drop_column("cdd_records", "exception_expires_on")
    op.drop_column("cdd_records", "exception_granted_at")
    op.drop_column("cdd_records", "exception_granted_by_id")
    op.drop_column("cdd_records", "exception_reason")
    op.drop_column("cdd_records", "exception_granted")
    op.drop_column("company_profiles", "regulator")
    op.drop_column("company_profiles", "entity_category")
