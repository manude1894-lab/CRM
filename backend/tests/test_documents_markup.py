"""Triam BRD mark-up §14 — document types, links, Compliance documents and removal history."""
import io

import pytest
from fastapi import HTTPException, UploadFile

from app.services import document_service
from tests import flow
from tests.test_p2_workflow import complete_client, people  # noqa: F401  (fixture)


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
    acc = complete_client(db, people["maker"])
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
    acc = complete_client(db, maker)
    doc = document_service.create_for_account(db, acc.id, _file("passport.pdf"), "PASSPORT", maker)
    document_service.delete(db, doc.id, maker)
    folder = document_service.client_folder(db, acc.id, maker)
    assert folder["documents"] == []
    [gone] = folder["removed"]
    assert gone["filename"] == "passport.pdf" and gone["removed_by_name"] == "Rita RM"
