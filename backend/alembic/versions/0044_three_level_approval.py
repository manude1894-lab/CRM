"""Triam BRD mark-up §7–§10: new clients are approved in two steps after the RM submits.

RM submits (mandatory RM/Sales comments + KYC declaration) → Compliance (MLRO) completes the CDD
section and approves with mandatory comments → Approver gives the final approval with mandatory
comments. approval_requests records which step a pending request is at and the Compliance decision;
checker_id / reason_text / decided_at keep holding the final decision.

Revision ID: 0044_three_level_approval
Revises: 0043_triam_markup_masters_roles
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0044_three_level_approval"
down_revision = "0043_triam_markup_masters_roles"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("approval_requests", sa.Column("stage", sa.String(20), nullable=True))
    op.add_column("approval_requests", sa.Column("kyc_declared", sa.Boolean(), nullable=True))
    op.add_column("approval_requests", sa.Column("compliance_checker_id", sa.Integer(),
                                                 sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("approval_requests", sa.Column("compliance_comment", sa.Text(), nullable=True))
    op.add_column("approval_requests", sa.Column("compliance_decided_at", sa.DateTime(timezone=True), nullable=True))
    # Client onboardings already with Compliance are at the Compliance step.
    op.execute("UPDATE approval_requests SET stage='Compliance' WHERE request_type='client_profile' AND status='Pending'")


def downgrade():
    for col in ("compliance_decided_at", "compliance_comment", "compliance_checker_id", "kyc_declared", "stage"):
        op.drop_column("approval_requests", col)
