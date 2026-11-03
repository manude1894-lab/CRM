"""Client-facing roles are marked with the client.portfolio permission (Triam, 03-11-2026).

Until now a role counted as client-facing when it had none of the central-desk permissions, one of
which was prospect.assign. Triam then gave prospect.assign to every role, so every RM looked like a
desk user (empty RM lists, desk menu). Client-facing is now an explicit permission on the role.

Existing roles get it when they carry no desk permission (approve, final approve, invoices, read-only),
except the Prospecting Coordinator, whose desk is assigning prospects.

Revision ID: 0062_rm_portfolio_permission
Revises: 0061_activate_reg_authorities
Create Date: 2026-11-03
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0062_rm_portfolio_permission"
down_revision = "0061_activate_reg_authorities"
branch_labels = None
depends_on = None

DESK = {"client.approve", "client.final_approve", "invoice.manage", "read_only"}
FLAG = "client.portfolio"


def _perms(value):
    return list(json.loads(value) if isinstance(value, str) else (value or []))


def upgrade():
    conn = op.get_bind()
    for role_id, name, permissions in conn.execute(sa.text("SELECT id, name, permissions FROM roles")).fetchall():
        perms = _perms(permissions)
        if FLAG in perms or (set(perms) & DESK) or name.strip().lower() == "prospecting coordinator":
            continue
        conn.execute(sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                     {"p": json.dumps(perms + [FLAG]), "id": role_id})


def downgrade():
    conn = op.get_bind()
    for role_id, permissions in conn.execute(sa.text("SELECT id, permissions FROM roles")).fetchall():
        perms = _perms(permissions)
        if FLAG in perms:
            conn.execute(sa.text("UPDATE roles SET permissions = :p WHERE id = :id"),
                         {"p": json.dumps([p for p in perms if p != FLAG]), "id": role_id})
