"""Triam BRD mark-up §4A: every new client starts as a prospect.

- prospects: who assigned the RM, when, and the optional Assignor's comments; the client created from
  the prospect. owner_id is the assigned RM and may now be empty (unassigned prospect).
- accounts.prospect_id: the prospect a client came from — its Prospect ID is the client's temporary
  ID until Compliance approves and the Client ID is issued.
- "Prospecting Coordinator" role (assigns prospects to RMs).

Revision ID: 0045_prospect_first
Revises: 0044_three_level_approval
Create Date: 2026-10-09
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0045_prospect_first"
down_revision = "0044_three_level_approval"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prospects", sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("prospects", sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("prospects", sa.Column("assignor_comments", sa.Text(), nullable=True))
    op.add_column("prospects", sa.Column("converted_account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True))
    op.add_column("accounts", sa.Column("prospect_id", sa.Integer(), sa.ForeignKey("prospects.id", ondelete="SET NULL"), nullable=True))
    # Existing prospects already have an RM: record it as assigned when the prospect was created.
    op.execute("UPDATE prospects SET assigned_at = created_at WHERE owner_id IS NOT NULL")
    bind = op.get_bind()
    if not bind.execute(sa.text("SELECT 1 FROM roles WHERE lower(name)='prospecting coordinator'")).first():
        bind.execute(sa.text("INSERT INTO roles (name, description, permissions, is_active) VALUES (:n, :d, :p, :a)"),
                     {"n": "Prospecting Coordinator", "d": "Prospecting Team Coordinator — assigns prospects to RMs",
                      "p": json.dumps(["prospect.assign"]), "a": True})


def downgrade():
    op.drop_column("accounts", "prospect_id")
    for col in ("converted_account_id", "assignor_comments", "assigned_at", "assigned_by_id"):
        op.drop_column("prospects", col)
