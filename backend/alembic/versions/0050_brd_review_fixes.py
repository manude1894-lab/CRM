"""BRD review fixes (Triam mark-up, line-by-line cross-check).

- §9  Engagement Letter Signed is a mandatory Yes / No: nullable so "not answered" differs from "No".
      Clients still being prepared are reset to "not answered"; approved clients keep their value.
- §14 Documents for the UBO / Director / Authorised Signatory / Joint Holder sections belong to that
      person: documents.party_id.
- §13 "Inquiry & Reports" is a read-only role: permission read_only on the Inquiry role.

Revision ID: 0050_brd_review_fixes
Revises: 0049_login_times
Create Date: 2026-10-12
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0050_brd_review_fixes"
down_revision = "0049_login_times"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("accounts", "engagement_letter_signed", existing_type=sa.Boolean(), nullable=True, server_default=None)
    op.execute("UPDATE accounts SET engagement_letter_signed = NULL "
               "WHERE profile_status IN ('New', 'WIP') AND engagement_letter_signed = false")
    op.add_column("documents", sa.Column("party_id", sa.Integer(), sa.ForeignKey("account_parties.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_documents_party_id", "documents", ["party_id"])
    bind = op.get_bind()
    row = bind.execute(sa.text("SELECT id, permissions FROM roles WHERE lower(name) = 'inquiry'")).first()
    if row:
        perms = row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]")
        if "read_only" not in perms:
            bind.execute(sa.text("UPDATE roles SET permissions = :p WHERE id = :i"), {"p": json.dumps(perms + ["read_only"]), "i": row[0]})


def downgrade():
    op.drop_index("ix_documents_party_id", "documents")
    op.drop_column("documents", "party_id")
    op.execute("UPDATE accounts SET engagement_letter_signed = false WHERE engagement_letter_signed IS NULL")
    op.alter_column("accounts", "engagement_letter_signed", existing_type=sa.Boolean(), nullable=False)
