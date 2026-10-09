"""Triam's BRD mark-up (Oct 2026) — entities, services by entity, departments, roles, multi-role users.

- Triam entities: TCPL, TMCL, IFZA, TABL, TCDL with full names (BRD §4, §17). TAB is renamed TABL
  everywhere it is stored (master list, clients' anchor / non-anchor entities, Client IDs and the
  Client ID counter). TMC stays inactive.
- Services: Triam's "Triam Entity – Services Provided Relationship" table. Each service records the
  entities that offer it in meta.entities. The earlier starter list is kept inactive so existing
  clients still show their services.
- Departments and roles from the "RM-MLRO Relationships" table (Approver, Inquiry, Accountant,
  Risk Officer, Rel. Manager). Existing rows are left as they are.
- users can hold more than one business role ("One email ID should be amenable to be assigned to
  more than one role"): user_extra_roles link table next to the main users.business_role_id.

Revision ID: 0043_triam_markup_masters_roles
Revises: 0042_recount_client_cases
Create Date: 2026-10-09
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0043_triam_markup_masters_roles"
down_revision = "0042_recount_client_cases"
branch_labels = None
depends_on = None

ENTITIES = [
    ("TCPL", "TCPL – Triam Consultancies Pvt Ltd (ADGM)"),
    ("TMCL", "TMCL – Triam Management Consultancies LLC"),
    ("IFZA", "IFZA – Triam Management Services FZCO"),
    ("TABL", "TABL – Triam Accounting & Book-keeping LLC"),
    ("TCDL", "TCDL – Triam Consultancies (DIFC) Ltd"),
]

SERVICES_BY_ENTITY = {
    "TMCL": ["Company Formation Services – DIFC, ADGM", "Outsourced CO/MLRO – DIFC, ADGM", "Outsourced RO – DIFC, ADGM",
             "Company Secretarial Services", "Name Screening Services", "Other Management Consultancies", "Audit Services"],
    "TABL": ["Outsourced FO", "Accounting & Book-keeping", "VAT Services", "Corporate Tax Services", "Audit Services"],
    "IFZA": ["Offshore Company Formation Services", "Onshore Company Formation Services", "Company License Renewals",
             "Corporate/ VAT Registrations", "Visa & Immigration Services", "Company liquidations", "Other Corporate Services"],
    "TCDL": ["Set up Foundations", "Set up SPVs", "Set up SPCs", "Company Formation Services", "Company License Renewals"],
    "TCPL": ["Set up Foundations", "Set up SPVs", "Set up SPCs", "Company Formation Services", "Company License Renewals"],
}

DEPARTMENTS = ["Co. Formation", "Compliance", "Finance", "Risk", "BVI", "ADGM CSP", "DIFC CSP", "Central Ops", "Accounts"]

ROLES = [
    ("Approver", "Final approval of new clients (Central Ops)", ["client.final_approve", "view.all_clients", "audit.view"]),
    ("Inquiry", "Inquiry & Reports (Central Ops) — sees all clients", ["view.all_clients"]),
    ("Accountant", "Invoice Module (Accounts)", ["invoice.manage", "view.all_clients"]),
    ("Risk Officer", "Risk department", []),
    ("Rel. Manager", "Relationship Manager (BVI, ADGM CSP, DIFC CSP)", []),
]


def _services():
    order, entities = [], {}
    for ent, names in SERVICES_BY_ENTITY.items():
        for n in names:
            if n not in entities:
                order.append(n)
                entities[n] = []
            entities[n].append(ent)
    return order, entities


def upgrade():
    bind = op.get_bind()
    q = lambda sql, **kw: bind.execute(sa.text(sql), kw)  # noqa: E731

    # ── Triam entities ──────────────────────────────────────────────────────
    if q("SELECT 1 FROM master_items WHERE list_type='triam_entity' AND code='TAB'").first():
        if q("SELECT 1 FROM master_items WHERE list_type='triam_entity' AND code='TABL'").first():
            q("DELETE FROM master_items WHERE list_type='triam_entity' AND code='TAB'")
        else:
            q("UPDATE master_items SET code='TABL' WHERE list_type='triam_entity' AND code='TAB'")
    for i, (code, label) in enumerate(ENTITIES):
        if q("SELECT 1 FROM master_items WHERE list_type='triam_entity' AND code=:c", c=code).first():
            q("UPDATE master_items SET label=:l, sort_order=:s, is_active=:a WHERE list_type='triam_entity' AND code=:c",
              l=label, s=(i + 1) * 10, a=True, c=code)
        else:
            q("INSERT INTO master_items (list_type, code, label, sort_order, is_active) VALUES ('triam_entity', :c, :l, :s, :a)",
              c=code, l=label, s=(i + 1) * 10, a=True)
    q("UPDATE master_items SET sort_order=90, is_active=:a WHERE list_type='triam_entity' AND code='TMC'", a=False)

    # TAB → TABL on stored data
    q("UPDATE accounts SET anchor_entity='TABL' WHERE anchor_entity='TAB'")
    for acc_id, raw in q("SELECT id, non_anchor_entities FROM accounts WHERE non_anchor_entities IS NOT NULL").fetchall():
        vals = raw if isinstance(raw, list) else json.loads(raw or "null")
        if vals and "TAB" in vals:
            new = ["TABL" if v == "TAB" else v for v in vals]
            q("UPDATE accounts SET non_anchor_entities=:v WHERE id=:i", v=json.dumps(new), i=acc_id)
    for acc_id, cid in q("SELECT id, client_id FROM accounts WHERE client_id LIKE 'TAB/%'").fetchall():
        q("UPDATE accounts SET client_id=:n WHERE id=:i", n="TABL/" + cid[4:], i=acc_id)
    if q("SELECT 1 FROM client_id_sequences WHERE entity_code='TAB'").first():
        if not q("SELECT 1 FROM client_id_sequences WHERE entity_code='TABL'").first():
            q("UPDATE client_id_sequences SET entity_code='TABL' WHERE entity_code='TAB'")

    # ── Services by entity ──────────────────────────────────────────────────
    order, entities = _services()
    q("UPDATE master_items SET is_active=:a WHERE list_type='service'", a=False)
    for i, name in enumerate(order):
        meta = json.dumps({"entities": entities[name]})
        if q("SELECT 1 FROM master_items WHERE list_type='service' AND code=:c", c=name).first():
            q("UPDATE master_items SET label=:c, sort_order=:s, is_active=:a, meta=:m WHERE list_type='service' AND code=:c",
              c=name, s=(i + 1) * 10, a=True, m=meta)
        else:
            q("INSERT INTO master_items (list_type, code, label, sort_order, is_active, meta) VALUES ('service', :c, :c, :s, :a, :m)",
              c=name, s=(i + 1) * 10, a=True, m=meta)

    # ── Departments and roles ───────────────────────────────────────────────
    for name in DEPARTMENTS:
        if not q("SELECT 1 FROM departments WHERE lower(name)=lower(:n)", n=name).first():
            q("INSERT INTO departments (name, is_active) VALUES (:n, :a)", n=name, a=True)
    for name, desc, perms in ROLES:
        if not q("SELECT 1 FROM roles WHERE lower(name)=lower(:n)", n=name).first():
            q("INSERT INTO roles (name, description, permissions, is_active) VALUES (:n, :d, :p, :a)",
              n=name, d=desc, p=json.dumps(perms), a=True)

    # ── Users with more than one role ───────────────────────────────────────
    op.create_table(
        "user_extra_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade():
    op.drop_table("user_extra_roles")
