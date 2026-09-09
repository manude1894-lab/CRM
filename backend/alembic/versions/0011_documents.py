"""Add documents table (uploaded files, bytes stored in Postgres).

Revision ID: 0011_documents
Revises: 0010_formation_compliance
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_documents"
down_revision = "0010_formation_compliance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_document_id", sa.Integer(), sa.ForeignKey("case_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("instruction_id", sa.Integer(), sa.ForeignKey("instructions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.String(40), nullable=False, server_default="Other"),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])


def downgrade():
    op.drop_index("ix_documents_case_id", table_name="documents")
    op.drop_table("documents")
