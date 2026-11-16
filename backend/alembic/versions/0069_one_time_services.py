"""Services catalogue and one-time services (Triam "CRM one-time service - changes 14-11-2026").

- Services Obtained is removed from the screen and the database. Nature of Services Sought is the one services
  field; anything a client had only under Services Obtained is copied into it first, so nothing is lost.
- Services renamed (master code and label, and on every client that holds them), one added.
- One-time services: each service holds the Triam entities for which it is a one-time service, in
  meta.one_time_entities (Admin -> Masters -> Services). Seeded from Triam's example table.

Revision ID: 0069_one_time_services
Revises: 0068_approval_fees_prospects
Create Date: 2026-11-16
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0069_one_time_services"
down_revision = "0068_approval_fees_prospects"
branch_labels = None
depends_on = None

RENAMES = [
    ("Corporate Tax Services", "Corporate Tax Return Filing"),
    ("Corporate/ VAT Registrations", "Corporate Tax Registration"),
    ("Outsourced FO", "Outsourced FO - DIFC, ADGM, Other"),
    ("VAT Registration & Filing", "VAT Registration"),
    ("VAT Services", "VAT Return Filing"),
    ("VAT Servcies", "VAT Return Filing"),
]
ANNUAL_RETURN = "Annual Return Filing - DIFC, ADGM & Other Reg Entities"
# Triam's table: service -> the Triam entities for which it is a one-time service.
ONE_TIME = {
    "Corporate Tax Registration": ["TABL"],
    "VAT Registration": ["TABL"],
    ANNUAL_RETURN: ["TMCL", "TCPL", "TABL"],
    "Other Management Consultancies": ["TMCL", "IFZA", "TCPL"],
    "Other Corporate Services": ["TMCL", "IFZA", "TCPL"],
}


def _load(raw):
    if raw is None or isinstance(raw, (list, dict)):
        return raw
    return json.loads(raw)


def _dedupe(values):
    return list(dict.fromkeys(v for v in values if v))


def upgrade():
    bind = op.get_bind()
    q = lambda sql, **kw: bind.execute(sa.text(sql), kw)  # noqa: E731

    # ── Services Obtained folded into Nature of Services Sought, then dropped ──
    for acc_id, obtained, sought in q("SELECT id, services_obtained, nature_of_services_sought FROM accounts "
                                      "WHERE services_obtained IS NOT NULL").fetchall():
        merged = _dedupe([*(_load(sought) or []), *(_load(obtained) or [])])
        if merged != (_load(sought) or []):
            q("UPDATE accounts SET nature_of_services_sought = :v WHERE id = :i", v=json.dumps(merged), i=acc_id)
    # Open amendments may hold a staged Services Obtained change: move it to the sought list.
    for req_id, payload in q("SELECT id, payload FROM approval_requests WHERE request_type = 'client_amendment' "
                             "AND status IN ('Draft', 'Pending') AND payload IS NOT NULL").fetchall():
        p = _load(payload) or {}
        staged = (p.get("account") or {})
        if "services_obtained" in staged:
            obtained = staged.pop("services_obtained") or []
            if obtained and "nature_of_services_sought" in staged:
                staged["nature_of_services_sought"] = _dedupe([*(staged["nature_of_services_sought"] or []), *obtained])
            q("UPDATE approval_requests SET payload = :p WHERE id = :i", p=json.dumps(p), i=req_id)
    op.drop_column("accounts", "services_obtained")

    # ── Renames ──
    for old, new in RENAMES:
        row = q("SELECT id FROM master_items WHERE list_type = 'service' AND code = :c", c=old).first()
        if not row:
            continue
        if q("SELECT 1 FROM master_items WHERE list_type = 'service' AND code = :c", c=new).first():
            q("UPDATE master_items SET is_active = false WHERE id = :i", i=row[0])
        else:
            q("UPDATE master_items SET code = :n, label = :n WHERE id = :i", n=new, i=row[0])
        for acc_id, sought in q("SELECT id, nature_of_services_sought FROM accounts WHERE nature_of_services_sought IS NOT NULL").fetchall():
            values = _load(sought) or []
            if old in values:
                q("UPDATE accounts SET nature_of_services_sought = :v WHERE id = :i",
                  v=json.dumps(_dedupe([new if v == old else v for v in values])), i=acc_id)

    # ── New service ──
    if not q("SELECT 1 FROM master_items WHERE list_type = 'service' AND code = :c", c=ANNUAL_RETURN).first():
        q("INSERT INTO master_items (list_type, code, label, sort_order, is_active, meta) "
          "VALUES ('service', :c, :c, 0, true, :m)", c=ANNUAL_RETURN, m=json.dumps({"entities": ["TMCL", "TCPL", "TABL"]}))

    # ── One-time services ──
    for code, entities in ONE_TIME.items():
        row = q("SELECT id, meta FROM master_items WHERE list_type = 'service' AND code = :c", c=code).first()
        if not row:
            continue
        meta = _load(row[1]) or {}
        meta["one_time_entities"] = entities
        if not meta.get("entities"):  # a service with no links is offered by every entity: link it as Triam listed
            meta["entities"] = entities
        q("UPDATE master_items SET meta = :m, is_active = true WHERE id = :i", m=json.dumps(meta), i=row[0])


def downgrade():
    op.add_column("accounts", sa.Column("services_obtained", sa.JSON(), nullable=True))
    bind = op.get_bind()
    for item_id, meta in bind.execute(sa.text("SELECT id, meta FROM master_items WHERE list_type = 'service'")).fetchall():
        m = _load(meta) or {}
        if "one_time_entities" in m:
            m.pop("one_time_entities")
            bind.execute(sa.text("UPDATE master_items SET meta = :m WHERE id = :i"), {"m": json.dumps(m), "i": item_id})
