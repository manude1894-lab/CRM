"""Triam BRD mark-up §14: document categories, where each is uploaded, links, Compliance documents.

- document_category master: every category records where it is uploaded (meta.section); new
  categories Application, Dual Use Goods declaration, Source of Funds, Source of Income, PEP Assessment
  Form, VAT Registration Certificate, and the Compliance-only CDD Form and AML Risk Assessment.
- documents.link_url: a document can be a link (e.g. the KYC verification video on SharePoint)
  instead of an uploaded file; content becomes optional.

Revision ID: 0047_document_categories_links
Revises: 0046_markup_profile_fields
Create Date: 2026-10-09
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0047_document_categories_links"
down_revision = "0046_markup_profile_fields"
branch_labels = None
depends_on = None

PARTY = "UBO, Director, Authorised Signatory, Individual"
BOTH = "Corporate & Individual"
# (code, label, section, extra meta) in the order Triam listed them
CATEGORIES = [
    ("APPLICATION", "Application", "Main Client", {}),
    ("COI", "Registration Certificate / Certificate of Incorporation", "Corporate", {}),
    ("LICENSE", "License Certificate", "Corporate", {}),
    ("MOA", "MoA", "Corporate", {}),
    ("AOA", "AoA", "Corporate", {}),
    ("DUAL_USE", "Declaration on dealing in Dual Use Goods", "Corporate", {}),
    ("IJARA", "Ijara", "Corporate, Individual", {}),
    ("INCUMBENCY", "Certificate of Incumbency", "Corporate", {}),
    ("PASSPORT", "Passport", PARTY, {}),
    ("EID", "EID / National ID", PARTY, {}),
    ("VISA", "Visa", PARTY, {}),
    ("ADDRESS_PROOF", "Address Proof", BOTH, {}),
    ("SOW", "Source of Wealth", BOTH, {}),
    ("SOF", "Source of Funds", BOTH, {}),
    ("SOI", "Source of Income", BOTH, {}),
    ("PEP_FORM", "PEP Assessment Form", BOTH, {}),
    ("VAT_CERT", "VAT Registration Certificate", "Corporate", {}),
    ("CT_CERT", "Corporate Tax Registration Certificate", "Corporate", {}),
    ("KYC_VIDEO", "KYC Verification Video Clip", BOTH, {"link_suggested": True}),
    ("CDD_FORM", "CDD Form", "Compliance", {"compliance_only": True}),
    ("AML_RISK", "AML Risk Assessment Template, duly filled", "Compliance", {"compliance_only": True}),
    ("ANY_OTHER", "Any Other", BOTH, {}),
]


def upgrade():
    bind = op.get_bind()
    q = lambda sql, **kw: bind.execute(sa.text(sql), kw)  # noqa: E731
    for i, (code, label, section, extra) in enumerate(CATEGORIES):
        meta = json.dumps({"section": section, **extra})
        if q("SELECT 1 FROM master_items WHERE list_type='document_category' AND code=:c", c=code).first():
            q("UPDATE master_items SET label=:l, sort_order=:s, meta=:m WHERE list_type='document_category' AND code=:c",
              l=label, s=(i + 1) * 10, m=meta, c=code)
        else:
            q("INSERT INTO master_items (list_type, code, label, sort_order, is_active, meta) "
              "VALUES ('document_category', :c, :l, :s, :a, :m)", c=code, l=label, s=(i + 1) * 10, a=True, m=meta)

    op.add_column("documents", sa.Column("link_url", sa.String(1000), nullable=True))
    op.alter_column("documents", "content", existing_type=sa.LargeBinary(), nullable=True)


def downgrade():
    op.alter_column("documents", "content", existing_type=sa.LargeBinary(), nullable=False)
    op.drop_column("documents", "link_url")
