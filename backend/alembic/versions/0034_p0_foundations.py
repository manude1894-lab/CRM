"""P0 foundations (BRD v1.1): audit log, master data lists, business roles.

- audit_log: append-only trail of material changes and events (BRD §13, §15)
- master_items: admin-managed lists (BRD §18), seeded from the values that were hardcoded in the
  frontend, plus the BRD §16 document categories and a starter licensing-authority list
- roles + users.business_role_id: CO / MLRO / RO / FO / Sales Manager / Dy MLRO with permission
  flags (BRD §15). Permission defaults are a proposal pending Triam (BRD §22 open item 2).

Revision ID: 0034_p0_foundations
Revises: 0033_non_anchor_rms
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0034_p0_foundations"
down_revision = "0033_non_anchor_rms"
branch_labels = None
depends_on = None


def _items(list_type, rows):
    """rows: [(code, label, is_active, meta)] — sort_order follows list order."""
    return [
        {"list_type": list_type, "code": code, "label": label, "sort_order": (i + 1) * 10,
         "is_active": active, "meta": meta}
        for i, (code, label, active, meta) in enumerate(rows)
    ]


def _same(values, active=True):
    return [(v, v, active, None) for v in values]


SEED_MASTERS = (
    # BRD §4: TCPL, TMCL, TAB, TCDL. TMC existed in the app before the BRD — kept inactive so old
    # clients still display it, pending Triam's confirmation.
    _items("triam_entity", _same(["TCPL", "TMCL", "TAB", "TCDL"]) + [("TMC", "TMC", False, None)])
    + _items("service", _same([
        "Company Formation", "Corporate Secretarial", "Accounting & Bookkeeping",
        "VAT Registration & Filing", "Corporate Tax Registration & Filing", "Compliance & AML Advisory",
        "Registered Agent Services", "Trust & Fiduciary Services", "Licensing & Regulatory Support", "Other",
    ]))
    + _items("tag", _same(["DIFC", "ADGM", "DNFBP", "Mainland", "Holding Co.", "SPV"])
             # The app previously used the misspelling "DNFPB"; kept inactive so old data still resolves.
             + [("DNFPB", "DNFPB (old spelling)", False, None)])
    + _items("regulator", _same(["DFSA", "FSRA", "CMA", "UAECB"]) + [("Other", "Other", True, {"opens_free_text": True})])
    # Starter list — Triam to supply the final values (BRD §22 open item 6).
    + _items("licensing_authority", _same([
        "DIFC", "ADGM", "Dubai Department of Economy & Tourism (DET)", "Abu Dhabi Department of Economic Development (ADDED)",
        "DMCC", "IFZA", "JAFZA", "DAFZA", "Dubai Silicon Oasis (DSO)", "Meydan Free Zone", "RAKEZ",
        "SHAMS", "SAIF Zone", "Ajman Free Zone",
    ]) + [("Other", "Other", True, {"opens_free_text": True})])
    # BRD §16. Short codes because labels exceed documents.category (40 chars). The pre-BRD categories
    # are seeded inactive: internal flows still use them, and old documents keep their labels.
    + _items("document_category", [
        ("COI", "Registration Certificate / Certificate of Incorporation", True, None),
        ("LICENSE", "License Certificate", True, None),
        ("MOA", "MoA", True, None),
        ("AOA", "AoA", True, None),
        ("IJARA", "Ijara", True, None),
        ("INCUMBENCY", "Certificate of Incumbency", True, None),
        ("PASSPORT", "Passport", True, None),
        ("EID", "EID / National ID", True, None),
        ("VISA", "Visa", True, None),
        ("ADDRESS_PROOF", "Address Proof", True, None),
        ("SOW", "Source of Wealth", True, None),
        ("CT_CERT", "Corporate Tax Registration Certificate", True, None),
        ("KYC_VIDEO", "KYC Verification Video Clip", True, None),
        ("ANY_OTHER", "Any Other", True, None),
    ] + [(v, v, False, {"builtin": True}) for v in [
        "CDD", "Activation Document", "Reference Letter", "Structure Chart", "Corporate Document",
        "KYC Form", "Filed Return / Confirmation", "Restoration", "Closure / Strike Off", "Other",
    ]])
    # Used by the P2 checker reject flow (BRD §12 step 13, §14 "meaningful reject reason").
    + _items("rejection_reason", _same([
        "Documents missing or incomplete", "Information does not match the documents",
        "Shareholding does not total 100%", "Screening / adverse media findings",
        "Risk assessment incomplete or incorrect", "Other (explain in comments)",
    ]))
)

# Proposed defaults — Triam to confirm (BRD §22 open items 2 & 3).
_CHECKER = ["client.approve", "document.delete_submitted", "audit.view", "view.all_clients"]
SEED_ROLES = [
    {"name": "CO", "description": "Compliance Officer", "permissions": _CHECKER},
    {"name": "MLRO", "description": "Money Laundering Reporting Officer", "permissions": _CHECKER},
    {"name": "Dy MLRO", "description": "Deputy MLRO", "permissions": _CHECKER},
    {"name": "RO", "description": "Relationship Officer", "permissions": []},
    {"name": "FO", "description": "Front Office", "permissions": []},
    {"name": "Sales Manager", "description": "Sees clients of RMs in their department", "permissions": ["view.department_clients"]},
]


def upgrade():
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("subject_type", sa.String(60), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_account_id", "audit_log", ["account_id"])
    op.create_index("ix_audit_log_subject", "audit_log", ["subject_type", "subject_id"])

    master_items = op.create_table(
        "master_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("list_type", sa.String(40), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("label", sa.String(150), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("list_type", "code", name="uq_master_items_type_code"),
    )
    op.create_index("ix_master_items_list_type", "master_items", ["list_type"])
    op.bulk_insert(master_items, SEED_MASTERS)

    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_roles_name", "roles", ["name"])
    op.bulk_insert(roles, [{**r, "is_active": True} for r in SEED_ROLES])

    op.add_column("users", sa.Column("business_role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="SET NULL"), nullable=True))

    # Data fix: the tag was stored with the old misspelling; move existing clients to the BRD spelling.
    op.execute("UPDATE accounts SET tags = REPLACE(tags, 'DNFPB', 'DNFBP') WHERE tags LIKE '%DNFPB%'")


def downgrade():
    op.execute("UPDATE accounts SET tags = REPLACE(tags, 'DNFBP', 'DNFPB') WHERE tags LIKE '%DNFBP%'")
    op.drop_column("users", "business_role_id")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_master_items_list_type", table_name="master_items")
    op.drop_table("master_items")
    op.drop_index("ix_audit_log_subject", table_name="audit_log")
    op.drop_index("ix_audit_log_account_id", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_index("ix_audit_log_occurred_at", table_name="audit_log")
    op.drop_table("audit_log")
