"""Screening date on the client, and a Screening Report document category (Triam UAT 05/06-11-2026).

The category is added only if there's no screening category yet: Triam's Admin may already have made one.

Revision ID: 0064_screening_date
Revises: 0063_rejected_status
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0064_screening_date"
down_revision = "0063_rejected_status"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("screening_date", sa.Date(), nullable=True))
    op.execute("""
        INSERT INTO master_items (list_type, code, label, sort_order, is_active, meta)
        SELECT 'document_category', 'SCREENING_REPORT', 'Screening Report',
               (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM master_items WHERE list_type = 'document_category'),
               true, '{"section": "Corporate & Individual"}'::json
        WHERE NOT EXISTS (SELECT 1 FROM master_items WHERE list_type = 'document_category' AND label ILIKE '%screening%')
    """)


def downgrade():
    op.drop_column("accounts", "screening_date")
    op.execute("DELETE FROM master_items WHERE list_type = 'document_category' AND code = 'SCREENING_REPORT'")
