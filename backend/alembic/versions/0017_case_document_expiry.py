"""CDD checklist — case_documents.expiry_date (passport / ID expiry, RM-entered).

Revision ID: 0017_case_document_expiry
Revises: 0016_generated_docs
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_case_document_expiry"
down_revision = "0016_generated_docs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("case_documents", sa.Column("expiry_date", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("case_documents", "expiry_date")
