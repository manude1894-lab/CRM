"""Close the remaining Vistra-form / Process-Manual coverage gaps.

- shareholders.consideration_paid (Data Input Sheet)
- directors.director_role (VIRRGIN Director/Alternate/Reserve)
- formation_records.first_board_meeting_date
- case_documents.waived + waived_reason (KYC Appendix C professional-introducer exemption)

Revision ID: 0018_document_form_gaps
Revises: 0017_case_document_expiry
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_document_form_gaps"
down_revision = "0017_case_document_expiry"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shareholders", sa.Column("consideration_paid", sa.Numeric(14, 2), nullable=True))
    op.add_column("directors", sa.Column("director_role", sa.String(20), nullable=False, server_default="Director"))
    op.add_column("formation_records", sa.Column("first_board_meeting_date", sa.Date(), nullable=True))
    op.add_column("case_documents", sa.Column("waived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("case_documents", sa.Column("waived_reason", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("case_documents", "waived_reason")
    op.drop_column("case_documents", "waived")
    op.drop_column("formation_records", "first_board_meeting_date")
    op.drop_column("directors", "director_role")
    op.drop_column("shareholders", "consideration_paid")
