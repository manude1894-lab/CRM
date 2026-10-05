"""P2 maker-checker (BRD v1.1 §11, §12, §15): approval_requests.

Clients already sitting in "Awaiting Approval" (set by hand before the workflow existed) get a
Pending request so an approver can act on them; otherwise they'd be locked with nothing to review.

Revision ID: 0036_p2_maker_checker
Revises: 0035_p1_client_capture
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0036_p2_maker_checker"
down_revision = "0035_p1_client_capture"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_type", sa.String(30), nullable=False, server_default="client_profile"),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("maker_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("maker_comment", sa.Text(), nullable=True),
        sa.Column("checker_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_code", sa.String(60), nullable=True),
        sa.Column("reason_text", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
    )
    op.create_index("ix_approval_requests_account_id", "approval_requests", ["account_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

    op.execute(
        "INSERT INTO approval_requests (account_id, request_type, status, maker_comment) "
        "SELECT id, 'client_profile', 'Pending', 'Created by migration: client was already Awaiting Approval' "
        "FROM accounts WHERE profile_status = 'Awaiting Approval'"
    )


def downgrade():
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_account_id", table_name="approval_requests")
    op.drop_table("approval_requests")
