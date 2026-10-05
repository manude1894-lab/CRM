"""P3 Compliance approvals (BRD v1.1 §13, §15, §16 + Triam's Compliance review desk).

- approval_requests now also carries client amendments and case approvals:
  account_id becomes optional, case_id / payload / changes / previous_request_id are added.
  Statuses gain Draft (an amendment being prepared) and Discarded.
- cases.compliance_status: a new case waits for Compliance approval before it can move through
  the pipeline. Existing cases are treated as already approved.

Revision ID: 0037_p3_compliance
Revises: 0036_p2_maker_checker
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0037_p3_compliance"
down_revision = "0036_p2_maker_checker"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("approval_requests") as t:
        t.alter_column("account_id", existing_type=sa.Integer(), nullable=True)
        t.add_column(sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=True))
        t.add_column(sa.Column("payload", sa.JSON(), nullable=True))
        t.add_column(sa.Column("changes", sa.JSON(), nullable=True))
        t.add_column(sa.Column("previous_request_id", sa.Integer(), nullable=True))
    op.create_index("ix_approval_requests_case_id", "approval_requests", ["case_id"])
    op.add_column("cases", sa.Column("compliance_status", sa.String(30), nullable=False, server_default="Approved"))


def downgrade():
    op.drop_column("cases", "compliance_status")
    op.drop_index("ix_approval_requests_case_id", table_name="approval_requests")
    op.execute("DELETE FROM approval_requests WHERE account_id IS NULL")
    with op.batch_alter_table("approval_requests") as t:
        t.drop_column("previous_request_id")
        t.drop_column("changes")
        t.drop_column("payload")
        t.drop_column("case_id")
        t.alter_column("account_id", existing_type=sa.Integer(), nullable=False)
