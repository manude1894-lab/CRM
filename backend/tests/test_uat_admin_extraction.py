"""UAT 05-11-2026 (UAT-16): data extraction and approved-case downloads are for Admins only."""
import pytest

from app.models import AuditLog, UserRole
from app.services import document_service
from tests import flow
from tests.helpers import auth


@pytest.fixture()
def desk(real_user, make_user):
    return {"maker": real_user("Rel. Manager"), "checker": real_user("MLRO"), "approver": real_user("Approver"),
            "inquiry": real_user("Inquiry"), "admin": make_user("Admin", role=UserRole.ADMIN)}


def _approved_doc(db, desk):
    acc = flow.approved_client(db, desk)
    return acc, acc.documents[0]


@pytest.mark.parametrize("who, code", [("maker", 403), ("checker", 403), ("approver", 403), ("inquiry", 403), ("admin", 200)])
def test_only_an_admin_downloads_from_an_approved_client(db, desk, client, who, code):
    _, doc = _approved_doc(db, desk)
    assert client.get(f"/api/v1/documents/{doc.id}/download", headers=auth(desk[who])).status_code == code


@pytest.mark.parametrize("who", ["maker", "checker", "approver", "inquiry", "admin"])
def test_everyone_who_sees_the_client_can_still_read_it(db, desk, client, who):
    _, doc = _approved_doc(db, desk)
    r = client.get(f"/api/v1/documents/{doc.id}/content", headers=auth(desk[who]))
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and "inline" in r.headers["content-disposition"]


def test_another_rm_still_can_not_read_it(db, desk, real_user, client):
    _, doc = _approved_doc(db, desk)
    assert client.get(f"/api/v1/documents/{doc.id}/content", headers=auth(real_user("Rel. Manager", "Other"))).status_code == 403


def test_before_approval_the_rm_can_download(db, desk, client):
    acc = flow.complete_client(db, desk["maker"])
    assert client.get(f"/api/v1/documents/{acc.documents[0].id}/download", headers=auth(desk["maker"])).status_code == 200


def test_an_invoice_file_stays_downloadable_on_an_approved_client(db, desk, client):
    from app.models import Invoice
    acc = flow.approved_client(db, desk)
    invoice = Invoice(account_id=acc.id, invoice_number="INV-1", status="Raised", currency="AED", amount=100)
    db.add(invoice)
    db.commit()
    doc = flow.add_document(db, acc, desk["maker"], invoice_id=invoice.id)
    assert client.get(f"/api/v1/documents/{doc.id}/download", headers=auth(desk["maker"])).status_code == 200


def test_folder_tells_the_screen_who_may_download(db, desk):
    acc, _ = _approved_doc(db, desk)
    assert document_service.client_folder(db, acc.id, desk["maker"])["documents"][0]["can_download"] is False
    assert document_service.client_folder(db, acc.id, desk["admin"])["documents"][0]["can_download"] is True


def test_a_download_is_recorded(db, desk, client):
    _, doc = _approved_doc(db, desk)
    client.get(f"/api/v1/documents/{doc.id}/download", headers=auth(desk["admin"]))
    assert db.query(AuditLog).filter(AuditLog.action == "document_download", AuditLog.subject_id == doc.id).count() == 1


@pytest.mark.parametrize("who, code", [("maker", 403), ("checker", 403), ("inquiry", 403), ("admin", 200)])
def test_audit_export_is_for_admins(desk, client, who, code):
    assert client.get("/api/v1/audit/export", headers=auth(desk[who])).status_code == code


def test_checker_can_still_view_the_audit_log(desk, client):
    assert client.get("/api/v1/audit", headers=auth(desk["checker"])).status_code == 200
