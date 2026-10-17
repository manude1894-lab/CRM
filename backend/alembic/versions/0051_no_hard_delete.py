"""No hard delete (Triam: "no delete option in a CRM"; BRD §2 / §13 "all material CRM activities and
changes must be recorded").

- Client parties and documents are removed by marking them (removed_at / removed_by_id / removed_reason);
  the record and the file stay in the database.
- Cases, service requests, action points, activities and invoices are cancelled with a reason instead
  of deleted (cancel_reason; status "Cancelled").
- §9 attachments: "Engagement Letter" and "Pricing approval / emails" document categories (Main Client).
- §14 "only an Approver-level user can remove [submitted documents]": the Approver role also gets
  document.delete_submitted (Compliance keeps it).

Revision ID: 0051_no_hard_delete
Revises: 0050_brd_review_fixes
Create Date: 2026-10-17
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0051_no_hard_delete"
down_revision = "0050_brd_review_fixes"
branch_labels = None
depends_on = None

REMOVABLE = ("account_parties", "documents")
CANCELLABLE = ("cases", "instructions", "action_points", "activities", "invoices")
NEW_CATEGORIES = [
    ("ENGAGEMENT_LETTER", "Engagement Letter"),
    ("PRICING", "Pricing approval / emails"),
]


def upgrade():
    for t in REMOVABLE:
        op.add_column(t, sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(t, sa.Column("removed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
        op.add_column(t, sa.Column("removed_reason", sa.String(500), nullable=True))
    for t in CANCELLABLE:
        op.add_column(t, sa.Column("cancel_reason", sa.String(500), nullable=True))

    bind = op.get_bind()
    q = lambda sql, **kw: bind.execute(sa.text(sql), kw)  # noqa: E731
    top = q("SELECT coalesce(max(sort_order), 0) FROM master_items WHERE list_type='document_category'").scalar()
    for i, (code, label) in enumerate(NEW_CATEGORIES):
        if not q("SELECT 1 FROM master_items WHERE list_type='document_category' AND code=:c", c=code).first():
            q("INSERT INTO master_items (list_type, code, label, sort_order, is_active, meta) "
              "VALUES ('document_category', :c, :l, :s, :a, :m)",
              c=code, l=label, s=top + (i + 1) * 10, a=True, m=json.dumps({"section": "Main Client"}))

    row = q("SELECT id, permissions FROM roles WHERE lower(name) = 'approver'").first()
    if row:
        perms = row[1] if isinstance(row[1], list) else json.loads(row[1] or "[]")
        if "document.delete_submitted" not in perms:
            q("UPDATE roles SET permissions = :p WHERE id = :i", p=json.dumps(perms + ["document.delete_submitted"]), i=row[0])


def downgrade():
    for t in CANCELLABLE:
        op.drop_column(t, "cancel_reason")
    for t in REMOVABLE:
        op.drop_column(t, "removed_reason")
        op.drop_column(t, "removed_by_id")
        op.drop_column(t, "removed_at")
    op.execute("DELETE FROM master_items WHERE list_type='document_category' AND code IN ('ENGAGEMENT_LETTER', 'PRICING')")
