"""BRD §14 — document types, links, Compliance documents and removal history."""
import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services import document_service
from tests import flow
from tests.flow import complete_client


def _file(name, ctype="application/pdf", data=b"%PDF-1.4 test"):
    return UploadFile(file=io.BytesIO(data), filename=name, headers={"content-type": ctype})


@pytest.fixture()
def cats(seed_master, db):
    seed_master("document_category", ["PASSPORT", "KYC_VIDEO"])
    from app.models import MasterItem
    db.add(MasterItem(list_type="document_category", code="CDD_FORM", label="CDD Form", sort_order=90, is_active=True,
                      meta={"section": "Compliance", "compliance_only": True}))
    db.commit()


def test_only_listed_file_types_are_accepted(db, people, cats):
    acc = complete_client(db, people["maker"])
    for name, ctype in (("notes.txt", "text/plain"), ("photo.gif", "image/gif"), ("data.csv", "text/csv")):
        with pytest.raises(HTTPException) as e:
            document_service.create_for_account(db, acc.id, _file(name, ctype), "PASSPORT", people["maker"])
        assert "Allowed: Word, Excel, PDF" in e.value.detail
    document_service.create_for_account(db, acc.id, _file("scan.bmp", "image/bmp", b"BM.."), "PASSPORT", people["maker"])


def test_kyc_video_can_be_a_sharepoint_link(db, people, cats):
    acc = complete_client(db, people["maker"], with_document=False)
    with pytest.raises(HTTPException):
        document_service.create_link_for_account(db, acc.id, "KYC_VIDEO", "http://insecure.example/x", None, people["maker"])
    doc = document_service.create_link_for_account(db, acc.id, "KYC_VIDEO", "https://triam.sharepoint.com/kyc/video-123",
                                                   "KYC call 01 10 2026", people["maker"])
    assert doc.link_url.endswith("video-123") and doc.size_bytes == 0
    [item] = document_service.client_folder(db, acc.id, people["maker"])["documents"]
    assert item["link_url"] == doc.link_url and item["filename"] == "KYC call 01 10 2026"
    with pytest.raises(HTTPException):
        document_service.stream_content(db, doc.id, people["maker"])


def test_compliance_documents_are_filed_by_compliance_during_review(db, people, cats):
    maker, checker = people["maker"], people["checker"]
    acc = complete_client(db, maker)
    with pytest.raises(HTTPException) as e:
        document_service.create_for_account(db, acc.id, _file("cdd.pdf"), "CDD_FORM", maker)
    assert "Compliance" in e.value.detail
    flow.submit(db, acc, maker)
    # the folder is locked for the RM, but Compliance files the CDD form during its review
    with pytest.raises(HTTPException):
        document_service.create_for_account(db, acc.id, _file("passport.pdf"), "PASSPORT", maker)
    document_service.create_for_account(db, acc.id, _file("cdd.pdf"), "CDD_FORM", checker)


def test_removed_documents_stay_in_the_folder_history(db, people, cats):
    maker = people["maker"]
    acc = complete_client(db, maker, with_document=False)
    doc = document_service.create_for_account(db, acc.id, _file("passport.pdf"), "PASSPORT", maker)
    document_service.delete(db, doc.id, maker)
    folder = document_service.client_folder(db, acc.id, maker)
    assert folder["documents"] == []
    [gone] = folder["removed"]
    assert gone["filename"] == "passport.pdf" and gone["removed_by_name"] == "Rita RM"


def test_compliance_can_take_back_a_wrong_compliance_document_during_review(db, people, cats):
    """Triam UAT 11-11-2026: a CDD Form uploaded by mistake couldn't be removed and replaced."""
    maker, checker, approver = people["maker"], people["checker"], people["approver"]
    acc = complete_client(db, maker)
    flow.submit(db, acc, maker)
    wrong = document_service.create_for_account(db, acc.id, _file("wrong-client-cdd.pdf"), "CDD_FORM", checker)
    by_name = lambda user: {d["filename"]: d for d in document_service.client_folder(db, acc.id, user)["documents"]}  # noqa: E731
    assert by_name(checker)["wrong-client-cdd.pdf"]["can_delete"] is True
    assert by_name(checker)["licence.pdf"]["can_delete"] is False  # the RM's documents stay frozen
    assert by_name(maker)["wrong-client-cdd.pdf"]["can_delete"] is False  # not the RM
    with pytest.raises(HTTPException):
        document_service.delete(db, wrong.id, maker)
    document_service.delete(db, wrong.id, checker, "Filed the wrong client's form")
    document_service.create_for_account(db, acc.id, _file("cdd.pdf"), "CDD_FORM", checker)
    folder = document_service.client_folder(db, acc.id, checker)
    assert "cdd.pdf" in [d["filename"] for d in folder["documents"]]
    assert [g["filename"] for g in folder["removed"]] == ["wrong-client-cdd.pdf"]  # kept on record

    # Once Compliance has approved, its documents are frozen like the rest.
    flow.fill_cdd(db, acc, checker)
    flow.compliance_approve(db, acc, checker)
    cdd = next(d for d in document_service.client_folder(db, acc.id, approver)["documents"] if d["filename"] == "cdd.pdf")
    with pytest.raises(HTTPException):
        document_service.delete(db, cdd["id"], checker)
