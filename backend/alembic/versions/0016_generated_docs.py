"""Document generation — documents.generated_from (template code, null = uploaded).

Revision ID: 0016_generated_docs
Revises: 0015_deeper_kyc
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_generated_docs"
down_revision = "0015_deeper_kyc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("generated_from", sa.String(60), nullable=True))


def downgrade():
    op.drop_column("documents", "generated_from")
