"""Add jurisdiction, service_type to cases; aml_risk_rating to cdd_records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_triam_fields"
down_revision = "0002_difc_onboarding_workflow"
branch_labels = None
depends_on = None


def upgrade():
    # Use IF NOT EXISTS so the migration is safe to re-run if a previous attempt
    # left the DB in a partial state.
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS jurisdiction VARCHAR(100)")
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS service_type VARCHAR(100)")
    op.execute("ALTER TABLE cdd_records ADD COLUMN IF NOT EXISTS aml_risk_rating VARCHAR(20)")


def downgrade():
    op.drop_column("cdd_records", "aml_risk_rating")
    op.drop_column("cases", "service_type")
    op.drop_column("cases", "jurisdiction")
