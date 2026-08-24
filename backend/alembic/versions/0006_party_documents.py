"""Link case_documents to a specific Director/Shareholder (per-party CDD checklist).

Revision ID: 0006_party_documents
Revises: 0005_instructions
Create Date: 2026-08-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_party_documents"
down_revision = "0005_instructions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("case_documents", sa.Column("director_id", sa.Integer(), sa.ForeignKey("directors.id", ondelete="CASCADE"), nullable=True))
    op.add_column("case_documents", sa.Column("shareholder_id", sa.Integer(), sa.ForeignKey("shareholders.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_case_documents_director_id", "case_documents", ["director_id"])
    op.create_index("ix_case_documents_shareholder_id", "case_documents", ["shareholder_id"])


def downgrade():
    op.drop_index("ix_case_documents_shareholder_id", table_name="case_documents")
    op.drop_index("ix_case_documents_director_id", table_name="case_documents")
    op.drop_column("case_documents", "shareholder_id")
    op.drop_column("case_documents", "director_id")
