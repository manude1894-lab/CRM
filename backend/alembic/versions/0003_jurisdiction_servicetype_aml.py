"""Add jurisdiction, service_type to cases; aml_risk_rating to cdd_records.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_jurisdiction_servicetype_aml"
down_revision = "0002_difc_onboarding_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("jurisdiction", sa.String(100), nullable=True))
    op.add_column("cases", sa.Column("service_type", sa.String(100), nullable=True))
    op.add_column("cdd_records", sa.Column("aml_risk_rating", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("cdd_records", "aml_risk_rating")
    op.drop_column("cases", "service_type")
    op.drop_column("cases", "jurisdiction")
