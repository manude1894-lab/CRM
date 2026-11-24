"""Standard reports as Excel or PDF (Triam UAT 19-11-2026, row 90). Only for users the Administrator has allowed
(permission report.export); each download is recorded in the audit log. The file holds exactly what the report
shows the user on screen: the same rows, limited to the clients they may see.

Triam 23-11-2026: a proper file layout. Both files open with the same heading block (Triam CRM, the report, the
filters used, who generated it and when, the number of rows, "Confidential"). Excel keeps real values: dates as
dates, numbers as numbers, blanks as empty cells (so filters and sums work), lists one item per line, and it prints
landscape, one page wide, with the column headings on every page and page numbers. The PDF sizes each column so
IDs, dates and headings are not broken mid-word, shades every other row, and numbers its pages.
"""
import io
import re
import statistics
from datetime import date, datetime
from typing import Optional

from fpdf import FPDF
from fpdf.fonts import FontFace
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.models import User
from app.services.standard_reports_service import BUSINESS_TZ

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_FORMAT = "DD MM YYYY"  # as on screen
BRAND = "1A3A5C"
BRAND_RGB = (0x1A, 0x3A, 0x5C)
APP = "Triam CRM"
CONFIDENTIAL = "Confidential - for Triam internal use"
BLANKS = ("—", "-", "")
LIST_SEPARATOR = "; "


def _as_date(v):
    return date.fromisoformat(v) if isinstance(v, str) and ISO_DATE.match(v) else None


def _shown(v) -> str:
    d = _as_date(v)
    if d:
        return d.strftime("%d %m %Y")
    return "" if v is None else str(v)


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() in BLANKS)


def _generated(user: User) -> str:
    return f"Generated {datetime.now(BUSINESS_TZ).strftime('%d %m %Y %H:%M')} (UAE) by {user.name}"


def _filters_line(filters: Optional[list]) -> str:
    return "Filters: " + ("; ".join(f"{k}: {v}" for k, v in filters) if filters else "none (everything you may see)")


def _rows_line(report: dict) -> str:
    n = len(report["rows"])
    return f"{n} row{'' if n == 1 else 's'}"


def filename(report: dict, ext: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", report["title"]).strip("-").lower()[:80] or "report"
    return f"triam-{slug}-{datetime.now(BUSINESS_TZ).strftime('%Y%m%d')}.{ext}"


# ── Excel ─────────────────────────────────────────────────────────────────────

def _cell_value(v):
    """What goes into the Excel cell: a date, a number, text (lists one item per line), or nothing."""
    if _is_blank(v):
        return None
    d = _as_date(v)
    if d:
        return d
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, str) and LIST_SEPARATOR in v:
        return "\n".join(v.split(LIST_SEPARATOR))
    return v


def to_xlsx(report: dict, user: User, filters: Optional[list] = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    cols = report["columns"]
    n = len(cols)
    last = get_column_letter(n)

    heading = [(APP, Font(bold=True, size=10, color=BRAND)), (report["title"], Font(bold=True, size=14)),
               (_filters_line(filters), Font(size=9, color="444444")),
               (f"{_generated(user)} - {_rows_line(report)}", Font(italic=True, size=9, color="666666")),
               (CONFIDENTIAL, Font(size=9, color="9A3412"))]
    for i, (text, font) in enumerate(heading, start=1):
        ws.cell(row=i, column=1, value=text).font = font
    head_row = len(heading) + 2

    thin = Side(style="thin", color="D9DEE5")
    border = Border(top=thin, bottom=thin, left=thin, right=thin)
    for j, c in enumerate(cols, start=1):
        cell = ws.cell(row=head_row, column=j, value=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = border
    ws.row_dimensions[head_row].height = 30

    stripe = PatternFill("solid", fgColor="F4F6F9")
    for i, row in enumerate(report["rows"]):
        r = head_row + 1 + i
        for j, v in enumerate(row, start=1):
            value = _cell_value(v)
            cell = ws.cell(row=r, column=j, value=value)
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=isinstance(value, str),
                                       horizontal="right" if isinstance(value, (int, float)) and not isinstance(value, bool) else None)
            if isinstance(value, date):
                cell.number_format = DATE_FORMAT
            elif isinstance(value, float):
                cell.number_format = "#,##0.00"
            if i % 2:
                cell.fill = stripe

    # Widths from the usual (not the longest) value, within limits; long text wraps instead of running off.
    for j, c in enumerate(cols, start=1):
        lengths = [max((len(x) for x in _shown(r[j - 1]).split(LIST_SEPARATOR)), default=0) for r in report["rows"]]
        typical = statistics.quantiles(lengths, n=10)[-1] if len(lengths) >= 10 else max(lengths, default=0)
        longest_word = max((len(w) for w in c.split()), default=0)
        ws.column_dimensions[get_column_letter(j)].width = min(max(typical, longest_word, 8) + 3, 45)

    ws.freeze_panes = ws.cell(row=head_row + 1, column=2)  # headings and the first column stay in view
    if report["rows"]:
        ws.auto_filter.ref = f"A{head_row}:{last}{ws.max_row}"

    # Printing: A4 landscape, one page wide, headings on every page, page numbers.
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{head_row}:{head_row}"
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.oddHeader.left.text = f"{APP} - {report['title']}"
    ws.oddHeader.left.size = 8
    ws.oddFooter.left.text = CONFIDENTIAL
    ws.oddFooter.left.size = 8
    ws.oddFooter.right.text = "Page &P of &N"
    ws.oddFooter.right.size = 8

    wb.properties.title = report["title"]
    wb.properties.creator = f"{APP} ({user.name})"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PDF ───────────────────────────────────────────────────────────────────────

# The PDF uses the built-in Helvetica, which covers Western European text; other characters are replaced.
_PDF_SUBSTITUTES = {"—": "-", "–": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", "•": "-"}


def _pdf_text(v) -> str:
    s = _shown(v)
    for a, b in _PDF_SUBSTITUTES.items():
        s = s.replace(a, b)
    s = s.replace(LIST_SEPARATOR, "\n")
    return s.encode("latin-1", "replace").decode("latin-1")


class _ReportPdf(FPDF):
    def __init__(self, title: str):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.report_title = title

    def header(self):
        if self.page_no() > 1:  # the first page has the full heading block
            self.set_font("Helvetica", "", 7)
            self.set_text_color(110, 110, 110)
            self.cell(0, 5, _pdf_text(f"{APP} - {self.report_title}"), new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-9)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(110, 110, 110)
        self.cell(self.epw / 2, 5, CONFIDENTIAL)
        self.cell(self.epw / 2, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def _column_widths(pdf: FPDF, cols: list, rows: list, font_size: float) -> list:
    """Each column at least as wide as its longest word (IDs, dates and headings are never broken), then the rest
    of the page shared out by how much text the column usually holds."""
    pdf.set_font("Helvetica", "", font_size)
    pad = 2.2
    minimum, wish = [], []
    for j, c in enumerate(cols):
        texts = [_pdf_text(r[j]) for r in rows]
        words = [w for t in texts for line in t.split("\n") for w in [line if len(line) <= 12 else ""] + line.split() if w]
        pdf.set_font("Helvetica", "B", font_size)
        head = max((pdf.get_string_width(w) for w in c.split()), default=0)
        pdf.set_font("Helvetica", "", font_size)
        word = max((pdf.get_string_width(w) for w in words), default=0)
        minimum.append(max(head, word) + pad)
        line_widths = [max((pdf.get_string_width(x) for x in t.split("\n")), default=0) for t in texts] or [0]
        typical = statistics.quantiles(line_widths, n=10)[-2] if len(line_widths) >= 10 else max(line_widths)
        wish.append(max(min(typical, 70) + pad, minimum[-1]))
    spare = pdf.epw - sum(minimum)
    if spare <= 0:
        return [m * pdf.epw / sum(minimum) for m in minimum]
    extra = [w - m for w, m in zip(wish, minimum)]
    total_extra = sum(extra) or 1
    if sum(wish) <= pdf.epw:  # everything fits: share the rest by how much text each column holds
        return [w * pdf.epw / sum(wish) for w in wish]
    return [m + spare * e / total_extra for m, e in zip(minimum, extra)]


def to_pdf(report: dict, user: User, filters: Optional[list] = None) -> bytes:
    pdf = _ReportPdf(report["title"])
    pdf.set_auto_page_break(auto=True, margin=13)
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*BRAND_RGB)
    pdf.cell(0, 5, APP, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, _pdf_text(report["title"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(70, 70, 70)
    pdf.multi_cell(0, 4.2, _pdf_text(_filters_line(filters)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 4.5, _pdf_text(f"{_generated(user)} - {_rows_line(report)}"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2.5)
    if not report["rows"]:
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, "Nothing to report.")
        return bytes(pdf.output())

    cols, rows = report["columns"], report["rows"]
    font_size = 7.5 if len(cols) <= 8 else 6.8
    widths = _column_widths(pdf, cols, rows, font_size)
    numeric = [all(isinstance(r[j], (int, float)) and not isinstance(r[j], bool) or _is_blank(r[j]) for r in rows)
               and any(isinstance(r[j], (int, float)) for r in rows) for j in range(len(cols))]
    pdf.set_font("Helvetica", "", font_size)
    pdf.set_draw_color(217, 222, 229)
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=BRAND_RGB)
    with pdf.table(col_widths=widths, width=pdf.epw, headings_style=heading, line_height=font_size * 0.5,
                   text_align=["RIGHT" if x else "LEFT" for x in numeric], repeat_headings=1,
                   cell_fill_color=(244, 246, 249), cell_fill_mode="ROWS", padding=0.9) as table:
        table.row([_pdf_text(c) for c in cols])
        for r in rows:
            table.row([_pdf_text(v) for v in r])
    return bytes(pdf.output())
