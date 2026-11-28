"""Supporting documents for a client amendment - Triam UAT 27-11-2026.

A document filed while amending an approved client is linked to that amendment, so Compliance sees it with the
changes it supports.

Revision ID: 0079_amendment_documents
Revises: 0078_report_settings
Create Date: 2026-11-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0079_amendment_documents"
down_revision = "0078_report_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("approval_request_id", sa.Integer(),
                                         sa.ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_documents_approval_request_id", "documents", ["approval_request_id"])


def downgrade():
    op.drop_index("ix_documents_approval_request_id", table_name="documents")
    op.drop_column("documents", "approval_request_id")
