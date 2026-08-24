"""Add instructions table (per-entity service-request tracker).

Revision ID: 0005_instructions
Revises: 0004_directors_shareholders
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_instructions"
down_revision = "0004_directors_shareholders"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "instructions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instruction_type", sa.String(150), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("document_shared", sa.Text(), nullable=True),
        sa.Column("date_received", sa.Date(), nullable=True),
        sa.Column("date_sent_to_vistra", sa.Date(), nullable=True),
        sa.Column("date_received_from_vistra", sa.Date(), nullable=True),
        sa.Column("date_completed", sa.Date(), nullable=True),
        sa.Column("charge_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("invoice_reference", sa.String(50), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_instructions_case_id", "instructions", ["case_id"])
    op.create_index("ix_instructions_status", "instructions", ["status"])


def downgrade():
    op.drop_index("ix_instructions_status", table_name="instructions")
    op.drop_index("ix_instructions_case_id", table_name="instructions")
    op.drop_table("instructions")
