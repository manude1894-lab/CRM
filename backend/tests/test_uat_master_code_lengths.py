"""Triam UAT 09/10-11-2026 (row 14): Admin's "Screening & Search Results - Non-Individuals" category is
44 characters; uploads under it failed because a document's category held only 40."""
from app.models import Document, MasterItem

LONG = "Screening & Search Results - Non-Individuals"


def test_a_document_takes_a_long_admin_category(db, make_user, make_account):
    rm = make_user("Rita RM")
    acc = make_account(name="Entity Client Ltd", spoc=rm)
    db.add(MasterItem(list_type="document_category", code=LONG, label=LONG, sort_order=99, is_active=True))
    db.add(Document(account_id=acc.id, category=LONG, filename="screening.pdf", content_type="application/pdf",
                    size_bytes=8, content=b"%PDF-1.4", uploaded_by_id=rm.id))
    db.commit()
    assert db.query(Document).filter(Document.category == LONG).count() == 1


def test_master_backed_columns_take_the_full_code_length():
    from app.models import Account, Instruction
    code_len = MasterItem.__table__.c.code.type.length
    for col in (Document.__table__.c.category, Account.__table__.c.anchor_entity, Account.__table__.c.regulator_name,
                Instruction.__table__.c.triam_entity, Instruction.__table__.c.status):
        assert col.type.length >= code_len, col
