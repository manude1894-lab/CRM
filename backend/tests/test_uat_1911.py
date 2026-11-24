"""Triam UAT issues log 19-11-2026.

- Row 90: reports can be downloaded as Excel or PDF, by the users the Administrator allows ("Can export reports").
- Rows 124-145: Client Tag in the reports, and Department (of the Anchor RM) in 3.7 and 3.8.
"""
import io
from datetime import datetime, timedelta, timezone

from openpyxl import load_workbook

from app.auth.permissions import REPORT_EXPORT, has_permission
from app.models import AuditLog, Department, MasterItem, UserRole
from app.schemas.user import UserUpdate
from app.services import standard_reports_service as rpt, user_service
from tests.helpers import auth, rows_of


def _tag(db, code, label):
    db.add(MasterItem(list_type="tag", code=code, label=label, sort_order=0, is_active=True))
    db.commit()


# ─── Who may download ───────────────────────────────────────────────────────────────────────────────────

def test_only_admins_and_ticked_users_may_export(db, make_user):
    admin, rm = make_user("Ada", role=UserRole.ADMIN), make_user("Rita RM")
    assert has_permission(admin, REPORT_EXPORT) and not has_permission(rm, REPORT_EXPORT)
    user_service.update_user(db, rm.id, UserUpdate(can_export_reports=True), admin)
    db.refresh(rm)
    assert rm.can_export_reports and has_permission(rm, REPORT_EXPORT) and REPORT_EXPORT in rm.permissions


def test_export_is_refused_without_the_tick(db, make_user, client):
    rm = make_user("Rita RM")
    r = client.get("/api/v1/reports/standard/clients-risk/export?format=xlsx", headers=auth(rm))
    assert r.status_code == 403 and "Administrator" in r.json()["detail"]


def test_excel_download_holds_the_report_and_is_logged(db, make_user, make_account, client):
    _tag(db, "FZ", "Freezone")
    rm = make_user("Rita RM")
    rm.can_export_reports = True
    db.commit()
    make_account(name="Due Soon", spoc=rm, profile_status="Active", anchor_entity="TCPL", tags="FZ",
                 next_aml_review_date=rpt._today() + timedelta(days=10))
    r = client.get("/api/v1/reports/standard/aml-reviews-due/export?format=xlsx&days=30", headers=auth(rm))
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in r.headers["content-disposition"] and ".xlsx" in r.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(r.content)).active
    # Triam 23-11-2026: a heading block (Triam CRM, title, filters, generated, confidential) above the table.
    assert ws["A1"].value == "Triam CRM" and ws["A2"].value == "AML reviews due in the next 30 days"
    assert ws["A3"].value == "Filters: Days: 30"
    head = next(r for r in range(1, 12) if ws.cell(row=r, column=1).value == "Anchor Triam Entity")
    header = [c.value for c in ws[head]]
    row = dict(zip(header, [c.value for c in ws[head + 1]]))
    assert row["Client Name"] == "Due Soon" and row["Client Tag"] == "Freezone" and row["Days left"] == 10
    assert ws.cell(row=head + 1, column=header.index("AML Expiry Date") + 1).number_format == "DD MM YYYY"  # a real date
    log = db.query(AuditLog).filter(AuditLog.action == "report_export").one()
    assert log.user_id == rm.id and "Excel" in log.summary


def test_pdf_download(db, make_user, make_account, client):
    admin = make_user("Ada", role=UserRole.ADMIN)
    make_account(name="Café — Ltd", profile_status="Active", next_aml_review_date=rpt._today() - timedelta(days=2))
    r = client.get("/api/v1/reports/standard/aml-reviews-expired/export?format=pdf", headers=auth(admin))
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    empty = client.get("/api/v1/reports/standard/rejected-with-rm/export?format=pdf", headers=auth(admin))
    assert empty.status_code == 200 and empty.content.startswith(b"%PDF")


def test_unknown_format_is_refused(db, make_user, client):
    admin = make_user("Ada", role=UserRole.ADMIN)
    assert client.get("/api/v1/reports/standard/clients-risk/export?format=docx", headers=auth(admin)).status_code == 400


# ─── Client Tag and Department in the reports ───────────────────────────────────────────────────────────

def test_reports_show_client_tag_and_department(db, make_user, make_account):
    _tag(db, "FZ", "Freezone")
    sales = Department(name="Sales")
    db.add(sales)
    db.commit()
    rm = make_user("Rita RM", department_id=sales.id)
    now = datetime.now(timezone.utc)
    make_account(name="Forming Co", spoc=rm, client_category="Under Formation", profile_status="Approved", tags="FZ, Unknown",
                 approved_at=now - timedelta(days=40), license_expiry_date=rpt._today() + timedelta(days=5))
    [doc] = rows_of(rpt.documents_expiring(db, rm))
    assert doc["Client Tag"] == "Freezone, Unknown"  # a code no longer in the list shows as it is
    [uf] = rows_of(rpt.run(db, rm, "under-formation"))
    assert (uf["Department"], uf["Client Tag"], uf["Anchor RM"]) == ("Sales", "Freezone, Unknown", "Rita RM")
    for key in ("documents-expired", "clients-risk", "aml-reviews-due", "aml-reviews-expired"):
        assert "Client Tag" in rpt.run(db, rm, key)["columns"], key
    assert {"Department", "Client Tag"} <= set(rpt.run(db, rm, "rejected-with-rm")["columns"])
    assert {"Department", "Client Tag"} <= set(rpt.run(db, rm, "prospects-unassigned")["columns"])
