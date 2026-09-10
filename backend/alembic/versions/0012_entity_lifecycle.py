"""Entity lifecycle — closure / strike-off / restoration / RA transfer.

- cases.status: drop the Postgres ENUM, make it a plain VARCHAR(30) so the
  lifecycle values (In Closure / Struck Off / Dissolved / Transferred Out) can be
  added without an ALTER TYPE (same precedent as jurisdiction / service_type).
- new entity_lifecycle table (1:1 with cases).

Revision ID: 0012_entity_lifecycle
Revises: 0011_documents
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision = "0012_entity_lifecycle"
down_revision = "0011_documents"
branch_labels = None
depends_on = None

_ORIGINAL_STATUS_VALUES = ("Active", "Docs Pending", "Rejected", "On Hold")
_case_status_enum = PGEnum(*_ORIGINAL_STATUS_VALUES, name="case_status", create_type=False)


def upgrade():
    # ─── cases.status: PG ENUM -> VARCHAR(30) ───────────────────────────
    # The column default ('Active'::case_status) depends on the enum type, so drop
    # it first, change the column type, re-add a plain default, then drop the type.
    op.execute("ALTER TABLE cases ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE cases ALTER COLUMN status TYPE VARCHAR(30) USING status::text")
    op.execute("ALTER TABLE cases ALTER COLUMN status SET DEFAULT 'Active'")
    op.execute("DROP TYPE IF EXISTS case_status")

    # ─── entity_lifecycle ──────────────────────────────────────────────
    op.create_table(
        "entity_lifecycle",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True),

        sa.Column("closure_method", sa.String(40), nullable=True),
        sa.Column("closure_initiated_date", sa.Date(), nullable=True),
        sa.Column("closure_reason", sa.Text(), nullable=True),
        sa.Column("client_acknowledgement_received", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("client_acknowledgement_date", sa.Date(), nullable=True),
        sa.Column("outstanding_filings_cleared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("strike_off_date", sa.Date(), nullable=True),
        sa.Column("strike_off_in_good_standing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expected_dissolution_date", sa.Date(), nullable=True),
        sa.Column("dissolution_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dissolution_date", sa.Date(), nullable=True),

        sa.Column("restoration_status", sa.String(20), nullable=False, server_default="Not Applicable"),
        sa.Column("restoration_initiated_date", sa.Date(), nullable=True),
        sa.Column("restoration_completed_date", sa.Date(), nullable=True),
        sa.Column("strike_off_cause", sa.String(20), nullable=True),
        sa.Column("restoration_checklist", sa.JSON(), nullable=True),

        sa.Column("transfer_from_agent", sa.String(50), nullable=True),
        sa.Column("transfer_to_agent", sa.String(50), nullable=True),
        sa.Column("transfer_initiated_date", sa.Date(), nullable=True),
        sa.Column("transfer_completed_date", sa.Date(), nullable=True),
        sa.Column("transfer_ends_administration", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("transfer_notes", sa.Text(), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("entity_lifecycle")

    # Recreate the enum and cast back. Rows carrying a lifecycle status
    # (In Closure / Struck Off / Dissolved / Transferred Out) must be resolved
    # to one of the original four values first or this will fail.
    PGEnum(*_ORIGINAL_STATUS_VALUES, name="case_status", create_type=True).create(
        op.get_bind(), checkfirst=True,
    )
    op.execute("ALTER TABLE cases ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TABLE cases ALTER COLUMN status TYPE case_status USING status::case_status")
    op.execute("ALTER TABLE cases ALTER COLUMN status SET DEFAULT 'Active'")
