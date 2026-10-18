"""Roles linked to their departments, as in the BRD roles table (§13); retire the unnamed TMC entity.

Only roles without a department are filled in. Rel. Manager serves three departments (BVI, ADGM CSP,
DIFC CSP) and is left unlinked; RO and Prospecting Coordinator have no department in the table.
TMC was never expanded to a full name in Triam's entity list; it is deactivated when no client uses it.

Revision ID: 0053_role_departments
Revises: 0052_sr_by_entity
Create Date: 2026-10-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0053_role_departments"
down_revision = "0052_sr_by_entity"
branch_labels = None
depends_on = None

ROLE_DEPARTMENT = {
    "Sales Manager": "Co. Formation",
    "CO": "Compliance",
    "Dy MLRO": "Compliance",
    "MLRO": "Central Ops",
    "FO": "Finance",
    "Risk Officer": "Risk",
    "Inquiry": "Central Ops",
    "Approver": "Central Ops",
    "Accountant": "Accounts",
}


def upgrade():
    bind = op.get_bind()
    for role, dept in ROLE_DEPARTMENT.items():
        bind.execute(sa.text(
            "UPDATE roles SET department_id = (SELECT id FROM departments WHERE name = :d) "
            "WHERE name = :r AND department_id IS NULL AND EXISTS (SELECT 1 FROM departments WHERE name = :d)"),
            {"r": role, "d": dept})
    bind.execute(sa.text(
        "UPDATE master_items SET is_active = false WHERE list_type = 'triam_entity' AND code = 'TMC' "
        "AND NOT EXISTS (SELECT 1 FROM accounts WHERE anchor_entity = 'TMC')"))


def downgrade():
    pass  # data only; departments on roles can be changed in Admin → Roles
