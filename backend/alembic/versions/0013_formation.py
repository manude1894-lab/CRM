"""Formation record — name/World-Check screening, MLRO sign-off, Vistra loop, §V milestones.

New formation_records table (1:1 with cases). No changes to existing tables.

Revision ID: 0013_formation
Revises: 0012_entity_lifecycle
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_formation"
down_revision = "0012_entity_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "formation_records",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True),

        sa.Column("screening_status", sa.String(20), nullable=False, server_default="Not Started"),
        sa.Column("screening_date", sa.Date(), nullable=True),
        sa.Column("screened_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("screening_tool", sa.String(60), nullable=True),
        sa.Column("world_check_reference", sa.String(120), nullable=True),
        sa.Column("sanctions_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pep_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("adverse_media_hit", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("screening_findings", sa.Text(), nullable=True),

        sa.Column("mlro_signoff_status", sa.String(20), nullable=False, server_default="Pending"),
        sa.Column("mlro_signoff_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mlro_signoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mlro_signoff_notes", sa.Text(), nullable=True),

        sa.Column("vistra_status", sa.String(30), nullable=False, server_default="Not Submitted"),
        sa.Column("vistra_submitted_date", sa.Date(), nullable=True),
        sa.Column("vistra_query_text", sa.Text(), nullable=True),
        sa.Column("vistra_query_raised_date", sa.Date(), nullable=True),
        sa.Column("vistra_query_resolved_date", sa.Date(), nullable=True),
        sa.Column("vistra_approved_date", sa.Date(), nullable=True),
        sa.Column("vistra_officer", sa.String(120), nullable=True),

        sa.Column("kyc_pack_sent_date", sa.Date(), nullable=True),
        sa.Column("data_input_sheet_sent_date", sa.Date(), nullable=True),
        sa.Column("incorporation_submitted_date", sa.Date(), nullable=True),
        sa.Column("rod_filed_date", sa.Date(), nullable=True),
        sa.Column("registers_completed_date", sa.Date(), nullable=True),
        sa.Column("formation_completed_date", sa.Date(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("formation_records")
