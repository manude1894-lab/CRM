"""Let Document belong to an Account directly, not only a Case (client spec §28 — Attachments).

case_id becomes nullable (relaxing an existing NOT NULL is non-destructive — no
existing rows are affected) and a new nullable account_id FK is added. Exactly
one of case_id/account_id is set per row, enforced at the service layer.

Revision ID: 0030_document_account_scope
Revises: 0029_nature_of_services_sought
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0030_document_account_scope"
down_revision = "0029_nature_of_services_sought"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("documents", "case_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("documents", sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True))
    op.create_index("ix_documents_account_id", "documents", ["account_id"])


def downgrade():
    op.drop_index("ix_documents_account_id", table_name="documents")
    op.drop_column("documents", "account_id")
    op.alter_column("documents", "case_id", existing_type=sa.Integer(), nullable=False)
