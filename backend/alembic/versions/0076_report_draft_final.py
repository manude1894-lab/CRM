"""Visit / Call Reports: Draft and final, corrections as notes (Triam 23-11-2026, S T Krishna).

"Save Draft" keeps a report editable (status Draft); "Save the Report" makes it final (Completed, finalised_at) and
from then on it is kept as written; a correction is a note beside it. Reports already Completed count as final.

Revision ID: 0076_report_draft_final
Revises: 0075_signed_out_at
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0076_report_draft_final"
down_revision = "0075_signed_out_at"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():  # a new enum value must be committed before it is used
        op.execute("ALTER TYPE activity_status ADD VALUE IF NOT EXISTS 'Draft'")
    op.add_column("activities", sa.Column("finalised_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("activities", sa.Column("finalised_by_id", sa.Integer(),
                                          sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.execute("UPDATE activities SET finalised_at = COALESCE(updated_at, created_at), finalised_by_id = owner_id "
               "WHERE status = 'Completed'")
    op.create_table(
        "activity_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("activity_corrections")
    op.drop_column("activities", "finalised_by_id")
    op.drop_column("activities", "finalised_at")
    # PostgreSQL cannot drop an enum value, so Draft stays in the type; drafts become Planned.
    op.execute("UPDATE activities SET status = 'Planned' WHERE status = 'Draft'")
