"""P6 Engagements: how a company comes to Triam.

cases.engagement_route — Formation (default, the existing pipeline), Existing Entity (already
serviced by Triam; created directly as Active from its real dates) or Transfer In (moving from
another registered agent). cases.previous_agent for transfers. cases.prior_filing_dates holds the
last renewal / ESR / Annual Return dates, used to build the Filing Calendar with overdue items.

Revision ID: 0039_p6_engagements
Revises: 0038_p5_servicing
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0039_p6_engagements"
down_revision = "0038_p5_servicing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("engagement_route", sa.String(30), nullable=False, server_default="Formation"))
    op.add_column("cases", sa.Column("previous_agent", sa.String(150), nullable=True))
    op.add_column("cases", sa.Column("prior_filing_dates", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("cases", "prior_filing_dates")
    op.drop_column("cases", "previous_agent")
    op.drop_column("cases", "engagement_route")
