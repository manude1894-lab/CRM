"""Add Account.non_anchor_rm_ids (client spec §I — Anchor/Non-anchor RM).

The Anchor RM is the existing Account.spoc_id; this adds the Non-anchor RM list.

Revision ID: 0033_non_anchor_rms
Revises: 0032_triam_entity
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_non_anchor_rms"
down_revision = "0032_triam_entity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("non_anchor_rm_ids", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("accounts", "non_anchor_rm_ids")
