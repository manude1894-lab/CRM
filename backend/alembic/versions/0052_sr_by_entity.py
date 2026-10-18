"""Service requests by Triam entity (Triam's "Service Requests – Triam Entities" list).

- Each request belongs to a Triam entity (instructions.triam_entity). Request types and statuses are
  master lists whose items name the entities they apply to (meta.entities; none ticked = all).
- "Other" opens a 50-character description (instructions.other_description).
- Statuses become Triam's: e.g. Received ... Completed / Dropped (TABL, IFZA) and Not started ...
  Pending with Vistra (TBVI). A cancelled request is "Dropped". Status column widened to 40.
- New Triam entity: TBVI – Trident Consultancy Services Ltd.
- The earlier generic request types are deactivated (kept for existing requests), except Other and
  Licence Renewal, which Triam's list keeps.

Revision ID: 0052_sr_by_entity
Revises: 0051_no_hard_delete
Create Date: 2026-10-18
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0052_sr_by_entity"
down_revision = "0051_no_hard_delete"
branch_labels = None
depends_on = None

UAE_DEFAULT = ["TABL", "IFZA", "TMCL", "TCDL", "TCPL"]  # TMCL / TCDL / TCPL until Triam sends their own lists

# (label, entities) in Triam's order; [] = every entity
TYPES = [
    ("Financial Audit", ["TABL"]),
    ("Financial Accounts Finalisation", ["TABL"]),
    ("Corporate Certificates (COI, COGS)", ["IFZA", "TBVI"]),
    ("Amendment of AOA, Bye-Laws", ["IFZA"]),
    ("Change in Shareholders / Directors", ["IFZA"]),
    ("CIT Registration", ["IFZA"]),
    ("VAT Registration", ["IFZA"]),
    ("Licence Renewal", ["IFZA"]),
    ("Licence Cancellation", ["IFZA"]),
    ("De-registration CT", ["IFZA"]),
    ("De-registration VAT", ["IFZA"]),
    ("FATCA CRS Filing", ["IFZA"]),
    ("Voluntary Strike Off", ["IFZA"]),
    ("Annual Accounts Filing", ["IFZA"]),
    ("Entity Name Change", ["IFZA"]),
    ("Changes in Org / Control Structure", ["TBVI"]),
    ("Transfer IN", ["TBVI"]),
    ("Transfer OUT", ["TBVI"]),
    ("Notary / Apostille Attestations", ["TBVI"]),
    ("Financial Filings", ["TBVI"]),
    ("Preparation of Financials", ["TBVI"]),
    ("LEI – New (Bloomberg)", ["TBVI"]),
    ("LEI – Renewal (Bloomberg)", ["TBVI"]),
    ("Strike Off / Liquidation", ["TBVI"]),
    ("Restoration", ["TBVI"]),
    ("Other", []),
]
STATUSES = [
    ("Received", UAE_DEFAULT),
    ("Applied for service", UAE_DEFAULT),
    ("Awaiting Invoice from Triam", UAE_DEFAULT),
    ("Pending with client", UAE_DEFAULT),
    ("Pending with Triam RM", UAE_DEFAULT),
    ("Pending with Auth", UAE_DEFAULT),
    ("Not started", ["TBVI"]),
    ("Doc pending from client", ["TBVI"]),
    ("Doc pending with us", ["TBVI"]),
    ("Initiated", ["TBVI"]),
    ("Client payment pending", ["TBVI"]),
    ("Pending with Vistra", ["TBVI"]),
    ("On Hold", []),
    ("Completed", []),
    ("Dropped", []),
]
OLD_TO_NEW = {"TBVI": {"Pending": "Not started", "In Progress": "Initiated"},
              None: {"Pending": "Received", "In Progress": "Applied for service"}}


def upgrade():
    op.alter_column("instructions", "status", existing_type=sa.String(20), type_=sa.String(40), existing_nullable=False)
    op.add_column("instructions", sa.Column("triam_entity", sa.String(20), nullable=True))
    op.add_column("instructions", sa.Column("other_description", sa.String(50), nullable=True))

    bind = op.get_bind()
    q = lambda sql, **kw: bind.execute(sa.text(sql), kw)  # noqa: E731

    def upsert(list_type, code, label, sort, meta):
        if q("SELECT 1 FROM master_items WHERE list_type=:t AND code=:c", t=list_type, c=code).first():
            q("UPDATE master_items SET label=:l, sort_order=:s, is_active=:a, meta=:m WHERE list_type=:t AND code=:c",
              t=list_type, c=code, l=label, s=sort, a=True, m=meta)
        else:
            q("INSERT INTO master_items (list_type, code, label, sort_order, is_active, meta) VALUES (:t, :c, :l, :s, :a, :m)",
              t=list_type, c=code, l=label, s=sort, a=True, m=meta)

    top = q("SELECT coalesce(max(sort_order), 0) FROM master_items WHERE list_type='triam_entity'").scalar()
    if not q("SELECT 1 FROM master_items WHERE list_type='triam_entity' AND code='TBVI'").first():
        upsert("triam_entity", "TBVI", "TBVI – Trident Consultancy Services Ltd", top + 10, None)

    keep = {label for label, _ in TYPES}
    q("UPDATE master_items SET is_active = :a WHERE list_type='service_request_type' AND code NOT IN :keep"
      .replace(":keep", "(" + ",".join(f"'{k}'" for k in keep) + ")"), a=False)
    for i, (label, entities) in enumerate(TYPES):
        upsert("service_request_type", label, label, (i + 1) * 10, json.dumps({"entities": entities}) if entities else None)
    for i, (label, entities) in enumerate(STATUSES):
        meta = {"entities": entities} if entities else {}
        if label in ("Completed", "Dropped"):
            meta["closed"] = True
        upsert("service_request_status", label, label, (i + 1) * 10, json.dumps(meta) if meta else None)

    # Existing requests: entity = TBVI for BVI case work, otherwise the client's anchor entity; statuses mapped.
    q("UPDATE instructions SET triam_entity = 'TBVI' WHERE case_id IS NOT NULL")
    q("UPDATE instructions SET triam_entity = a.anchor_entity FROM accounts a "
      "WHERE instructions.triam_entity IS NULL AND instructions.account_id = a.id")
    for old, new in OLD_TO_NEW["TBVI"].items():
        q("UPDATE instructions SET status=:n WHERE status=:o AND triam_entity='TBVI'", n=new, o=old)
    for old, new in OLD_TO_NEW[None].items():
        q("UPDATE instructions SET status=:n WHERE status=:o AND (triam_entity IS NULL OR triam_entity <> 'TBVI')", n=new, o=old)
    q("UPDATE instructions SET status='Dropped' WHERE status='Cancelled'")


def downgrade():
    op.execute("UPDATE instructions SET status='Pending' WHERE status IN ('Received', 'Not started')")
    op.execute("UPDATE instructions SET status='Cancelled' WHERE status='Dropped'")
    op.execute("UPDATE instructions SET status='In Progress' WHERE status NOT IN ('Pending', 'Completed', 'On Hold', 'Cancelled')")
    op.execute("DELETE FROM master_items WHERE list_type='service_request_status'")
    op.drop_column("instructions", "other_description")
    op.drop_column("instructions", "triam_entity")
    op.alter_column("instructions", "status", existing_type=sa.String(40), type_=sa.String(20), existing_nullable=False)
