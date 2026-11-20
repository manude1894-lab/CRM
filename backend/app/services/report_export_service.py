"""Standard reports as Excel or PDF (Triam UAT 19-11-2026, row 90). Only for users the Administrator has allowed
(permission report.export); each download is recorded in the audit log. The file holds exactly what the report
shows the user on screen: the same rows, limited to the clients they may see."""
import io
import re
from datetime import date, datetime

from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models import User
from app.services.standard_reports_service import BUSINESS_TZ

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_FORMAT = "DD MM YYYY"  # as on screen
BRAND = "1A3A5C"


def _as_date(v):
    return date.fromisoformat(v) if isinstance(v, str) and ISO_DATE.match(v) else None


def _shown(v) -> str:
    d = _as_date(v)
    if d:
        return d.strftime("%d %m %Y")
    return "" if v is None else str(v)


def _generated(user: User) -> str:
    return f"Generated {datetime.now(BUSINESS_TZ).strftime('%d %m %Y %H:%M')} (UAE) by {user.name}"


def filename(report: dict, ext: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", report["title"]).strip("-").lower()[:80] or "report"
    return f"{slug}-{datetime.now(BUSINESS_TZ).strftime('%Y%m%d')}.{ext}"


def to_xlsx(report: dict, user: User) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append([report["title"]])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([_generated(user)])
    ws["A2"].font = Font(italic=True, color="666666")
    ws.append([])
    ws.append(report["columns"])
    for cell in ws[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for row in report["rows"]:
        ws.append([_as_date(v) or v for v in row])
        for cell in ws[ws.max_row]:
            if isinstance(cell.value, date):
                cell.number_format = DATE_FORMAT
    for i, col in enumerate(report["columns"], start=1):
        longest = max([len(str(col))] + [len(_shown(r[i - 1])) for r in report["rows"]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(longest + 2, 10), 60)
    ws.freeze_panes = "A5"
    if report["rows"]:
        ws.auto_filter.ref = f"A4:{get_column_letter(len(report['columns']))}{ws.max_row}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# The PDF uses the built-in Helvetica, which covers Western European text; other characters are replaced.
_PDF_SUBSTITUTES = {"—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "•": "-"}


def _pdf_text(v) -> str:
    s = _shown(v)
    for a, b in _PDF_SUBSTITUTES.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: dict, user: User) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, _pdf_text(report["title"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, _pdf_text(f"{_generated(user)} - {len(report['rows'])} row{'' if len(report['rows']) == 1 else 's'}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)
    if not report["rows"]:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, "Nothing to report.")
        return bytes(pdf.output())
    # Column widths follow the content, within limits, scaled to the page.
    n = len(report["columns"])
    weights = [min(max(len(c), *(len(_pdf_text(r[i])) for r in report["rows"])), 40) + 2 for i, c in enumerate(report["columns"])]
    total = sum(weights)
    widths = [w * pdf.epw / total for w in weights]
    pdf.set_font("Helvetica", "", 7)
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(0x1A, 0x3A, 0x5C))
    with pdf.table(col_widths=widths, headings_style=heading, line_height=4, text_align=["LEFT"] * n,
                   repeat_headings=1) as table:
        table.row([_pdf_text(c) for c in report["columns"]])
        for r in report["rows"]:
            table.row([_pdf_text(v) for v in r])
    return bytes(pdf.output())
