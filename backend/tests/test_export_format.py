"""Triam 23-11-2026: report downloads in a proper format. Excel keeps real values (dates, numbers, empty cells),
puts lists one per line, and prints landscape, one page wide, with headings on every page; both files say which
filters were used; the PDF numbers its pages."""
import io
from types import SimpleNamespace

from openpyxl import load_workbook

from app.services import report_export_service as x

REPORT = {"title": "Clients with risk levels", "columns": ["Client Name", "Services applied", "Approved", "Days overdue", "Note"],
          "rows": [["Alpha Ltd", "Accounting; Annual Audit Support", "2026-11-01", 4, "—"],
                   ["Beta FZE", "—", None, 0, "Long note " * 20]]}
USER = SimpleNamespace(name="Ada Admin")


def _sheet(filters=None):
    return load_workbook(io.BytesIO(x.to_xlsx(REPORT, USER, filters))).active


def test_excel_has_the_heading_block_and_the_filters():
    ws = _sheet([("Status", "Active"), ("Anchor RM", "Rita")])
    texts = [ws.cell(row=i, column=1).value for i in range(1, 6)]
    assert texts[0] == "Triam CRM" and texts[1] == "Clients with risk levels"
    assert texts[2] == "Filters: Status: Active; Anchor RM: Rita"
    assert "by Ada Admin - 2 rows" in texts[3] and texts[4].startswith("Confidential")


def test_excel_keeps_real_values():
    ws = _sheet()
    head = next(r for r in range(1, 12) if ws.cell(row=r, column=1).value == "Client Name")
    first, second = head + 1, head + 2
    assert ws.cell(row=first, column=2).value == "Accounting\nAnnual Audit Support"  # one per line
    assert ws.cell(row=first, column=3).number_format == "DD MM YYYY" and ws.cell(row=first, column=3).value.year == 2026
    assert ws.cell(row=first, column=4).value == 4  # a number, not text
    assert ws.cell(row=first, column=5).value is None and ws.cell(row=second, column=2).value is None  # blanks are empty
    assert ws.cell(row=second, column=5).alignment.wrap_text


def test_excel_prints_properly():
    ws = _sheet()
    assert ws.page_setup.orientation == "landscape" and ws.page_setup.fitToWidth == 1
    assert ws.print_title_rows and "Page &P of &N" in ws.oddFooter.right.text
    assert ws.freeze_panes and ws.auto_filter.ref


def test_pdf_is_made_and_names_the_filters():
    pdf = x.to_pdf(REPORT, USER, [("Status", "Active")])
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    assert x.filename(REPORT, "pdf").startswith("triam-clients-with-risk-levels-")


def test_the_route_prints_the_filters(client, db, make_user):
    from tests.helpers import auth
    admin = make_user("Ada Admin", role="admin")
    r = client.get("/api/v1/reports/standard/onboarding-in-progress/export", params={"format": "xlsx", "status": "WIP"},
                   headers=auth(admin))
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.cell(row=3, column=1).value == "Filters: Status: WIP"
