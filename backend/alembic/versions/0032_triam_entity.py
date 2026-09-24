"""Add Account.anchor_entity / non_anchor_entities (client CRM-change-request item 3).

Revision ID: 0032_triam_entity
Revises: 0031_single_point_of_contact
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0032_triam_entity"
down_revision = "0031_single_point_of_contact"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("anchor_entity", sa.String(10), nullable=True))
    op.add_column("accounts", sa.Column("non_anchor_entities", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("accounts", "non_anchor_entities")
    op.drop_column("accounts", "anchor_entity")
