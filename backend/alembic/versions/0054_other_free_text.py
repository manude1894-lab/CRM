"""Free-text "please specify" for drop-downs whose "Other" choice had nowhere to record the answer:
case source, BVI company registered agent and nature of business, and strike-off cause.

Revision ID: 0054_other_free_text
Revises: 0053_role_departments
Create Date: 2026-10-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0054_other_free_text"
down_revision = "0053_role_departments"
branch_labels = None
depends_on = None

COLUMNS = [("cases", "source_other"), ("company_profiles", "registered_agent_other"),
           ("company_profiles", "nature_of_business_other"), ("entity_lifecycle", "strike_off_cause_other")]


def upgrade():
    for table, column in COLUMNS:
        op.add_column(table, sa.Column(column, sa.String(100), nullable=True))


def downgrade():
    for table, column in COLUMNS:
        op.drop_column(table, column)
