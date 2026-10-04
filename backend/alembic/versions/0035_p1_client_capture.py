"""P1 client capture (BRD v1.1): Client ID, Unique Search Name, duplicate exception,
licensing-authority "Other", KYC verified by, status-last-updated.

- accounts.client_id        BRD §19 {ENTITY}/{00000}, per-entity counter (client_id_sequences)
- accounts.search_name      BRD §3 unique short name; backfilled from the legal name
- accounts.company_name     no longer unique — duplicates allowed only via the approver exception
- accounts.duplicate_override_reason, licensing_authority_other, kyc_verified_by,
  status_updated_at, status_updated_by_id

Revision ID: 0035_p1_client_capture
Revises: 0034_p0_foundations
Create Date: 2026-10-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0035_p1_client_capture"
down_revision = "0034_p0_foundations"
branch_labels = None
depends_on = None


def _drop_company_name_uniqueness(bind):
    """0001 declared company_name unique+indexed. Depending on the dialect that is a unique
    index or a unique constraint — drop whichever exists, then keep a plain index."""
    insp = sa.inspect(bind)
    for uc in insp.get_unique_constraints("accounts"):
        if uc["column_names"] == ["company_name"]:
            op.drop_constraint(uc["name"], "accounts", type_="unique")
    for ix in insp.get_indexes("accounts"):
        if ix["column_names"] == ["company_name"]:
            op.drop_index(ix["name"], table_name="accounts")
    op.create_index("ix_accounts_company_name", "accounts", ["company_name"], unique=False)


def upgrade():
    bind = op.get_bind()

    op.create_table(
        "client_id_sequences",
        sa.Column("entity_code", sa.String(60), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column("accounts", sa.Column("client_id", sa.String(20), nullable=True))
    op.add_column("accounts", sa.Column("search_name", sa.String(120), nullable=True))
    op.add_column("accounts", sa.Column("duplicate_override_reason", sa.String(255), nullable=True))
    op.add_column("accounts", sa.Column("licensing_authority_other", sa.String(100), nullable=True))
    op.add_column("accounts", sa.Column("kyc_verified_by", sa.String(150), nullable=True))
    op.add_column("accounts", sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("accounts", sa.Column("status_updated_by_id", sa.Integer(),
                                        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))

    _drop_company_name_uniqueness(bind)

    # ── Backfill existing clients ──
    rows = bind.execute(sa.text("SELECT id, company_name, anchor_entity, updated_at FROM accounts ORDER BY id")).fetchall()
    used_names: set[str] = set()
    counters: dict[str, int] = {}
    for r in rows:
        base = " ".join((r.company_name or "").split())[:100] or f"Client {r.id}"
        name, n = base, 2
        while name.lower() in used_names:
            name = f"{base} ({n})"
            n += 1
        used_names.add(name.lower())
        client_id = None
        if r.anchor_entity:
            counters[r.anchor_entity] = counters.get(r.anchor_entity, 0) + 1
            client_id = f"{r.anchor_entity}/{counters[r.anchor_entity]:05d}"
        bind.execute(
            sa.text("UPDATE accounts SET search_name = :n, client_id = :c, status_updated_at = :u WHERE id = :id"),
            {"n": name, "c": client_id, "u": r.updated_at, "id": r.id},
        )
    for code, last in counters.items():
        bind.execute(sa.text("INSERT INTO client_id_sequences (entity_code, last_value) VALUES (:c, :v)"), {"c": code, "v": last})

    op.create_index("ix_accounts_client_id", "accounts", ["client_id"], unique=True)
    op.create_index("ix_accounts_search_name", "accounts", ["search_name"], unique=True)


def downgrade():
    op.drop_index("ix_accounts_search_name", table_name="accounts")
    op.drop_index("ix_accounts_client_id", table_name="accounts")
    op.drop_index("ix_accounts_company_name", table_name="accounts")
    # Restoring uniqueness fails if duplicates were created via the exception route — by design,
    # resolve those first.
    op.create_index("ix_accounts_company_name", "accounts", ["company_name"], unique=True)
    for col in ("status_updated_by_id", "status_updated_at", "kyc_verified_by", "licensing_authority_other",
                "duplicate_override_reason", "search_name", "client_id"):
        op.drop_column("accounts", col)
    op.drop_table("client_id_sequences")
