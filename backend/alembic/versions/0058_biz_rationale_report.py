"""Biz Rationale Report on the client (Triam UAT 26-10-2026).

Person met, date / time / place and mode of the meeting, and the business rationale for the relationship.

Revision ID: 0058_biz_rationale_report
Revises: 0057_drop_pre_brd_client_fields
Create Date: 2026-10-26
"""
import sqlalchemy as sa
from alembic import op

revision = "0058_biz_rationale_report"
down_revision = "0057_drop_pre_brd_client_fields"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("br_person_met", sa.String(255)),
    ("br_meeting_date", sa.Date()),
    ("br_meeting_time", sa.String(5)),
    ("br_meeting_place", sa.String(255)),
    ("br_meeting_mode", sa.String(20)),
    ("br_rationale", sa.Text()),
]


def upgrade():
    for name, type_ in _COLUMNS:
        op.add_column("accounts", sa.Column(name, type_, nullable=True))


def downgrade():
    for name, _ in reversed(_COLUMNS):
        op.drop_column("accounts", name)
