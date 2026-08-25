"""PDF report generation using ReportLab.

Produces:
- Case Stage Summary report
- Case Details report
- Compliance Calendar report
- RM/Ops Performance report
"""
from io import BytesIO
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER

from app.models import Case

# EZEETECH brand color
PRIMARY = colors.HexColor("#2B6D9A")
ACCENT = colors.HexColor("#10B981")
MUTED = colors.HexColor("#6B7280")
LIGHT = colors.HexColor("#F3F4F6")
DARK = colors.HexColor("#111827")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BrandTitle", parent=styles["Title"],
        fontName="Helvetica-Bold", fontSize=22, textColor=PRIMARY, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="BrandSub", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9, textColor=MUTED, spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="H2", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=13, textColor=DARK, spaceBefore=12, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="Body", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5, textColor=DARK, leading=13,
    ))
    styles.add(ParagraphStyle(
        name="KPILabel", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, textColor=MUTED, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="KPIValue", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=14, textColor=PRIMARY, alignment=TA_CENTER,
    ))
    return styles


def _fmt_money(n) -> str:
    v = float(n or 0)
    if v >= 1e6:
        return f"${v/1e6:.2f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"


def _fmt_full(n) -> str:
    return f"${float(n or 0):,.2f}"


def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PRIMARY)
    canvas.rect(0, A4[1] - 10, A4[0], 10, fill=1, stroke=0)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "TRIAM — Entity Servicing & Compliance Tracker")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"Generated {date.today().isoformat()}")
    canvas.restoreState()


def _kpi_row(kpis: list[tuple[str, str]]):
    styles = _styles()
    data = [
        [Paragraph(label, styles["KPILabel"]) for label, _ in kpis],
        [Paragraph(value, styles["KPIValue"]) for _, value in kpis],
    ]
    t = Table(data, colWidths=[(A4[0] - 4 * cm) / len(kpis)] * len(kpis))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _brand_header(styles, title: str, subtitle: str):
    return [
        Paragraph("TRIAM", styles["BrandSub"]),
        Paragraph(title, styles["BrandTitle"]),
        Paragraph(subtitle, styles["BrandSub"]),
    ]


def _data_table(headers: list[str], rows: list[list], col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8.5),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _new_doc(buf):
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )


# ─── Reports ─────────────────────────────────────────────────────────────
def case_stage_summary_pdf(dashboard: dict) -> bytes:
    """Generate the Case Stage Summary PDF."""
    buf = BytesIO()
    doc = _new_doc(buf)
    styles = _styles()
    elements = []
    elements += _brand_header(styles, "Case Stage Summary Report", f"Onboarding pipeline overview · {date.today().isoformat()}")

    kpis = dashboard["kpis"]
    elements.append(_kpi_row([
        ("Open Cases", str(kpis["open_cases"])),
        ("Docs Pending", str(kpis["docs_pending"])),
        ("CDD Awaiting Screening", str(kpis["cdd_awaiting_screening"])),
        ("Invoices Unpaid", str(kpis["invoices_unpaid"])),
    ]))
    elements.append(Spacer(1, 0.8 * cm))

    elements.append(Paragraph("Cases by Stage", styles["H2"]))
    headers = ["Stage", "Cases"]
    rows = [[s["stage"], str(s["count"])] for s in dashboard["stage_breakdown"] if s["count"] > 0]
    elements.append(_data_table(headers, rows, col_widths=[12 * cm, 4 * cm]))

    elements.append(Spacer(1, 0.6 * cm))
    elements.append(Paragraph("Upcoming Renewals / Filings (next 60 days)", styles["H2"]))
    comp_rows = [
        [c["case_uid"], c["company_name"], c["item"].replace("_", " ").title(), c["due_date"].isoformat(), str(c["days_remaining"])]
        for c in dashboard["upcoming_compliance"]
    ]
    elements.append(_data_table(
        ["Case", "Company", "Item", "Due Date", "Days Left"],
        comp_rows,
        col_widths=[2.5 * cm, 5.5 * cm, 4 * cm, 2.5 * cm, 2.5 * cm],
    ))

    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def case_details_pdf(cases: list[Case]) -> bytes:
    buf = BytesIO()
    doc = _new_doc(buf)
    styles = _styles()
    elements = []
    elements += _brand_header(
        styles, "Case Details Report",
        f"{len(cases)} cases · {date.today().isoformat()}",
    )

    headers = ["ID", "Company", "Stage", "Status", "Invoice", "RM", "Created"]
    rows = []
    for c in cases:
        rows.append([
            c.case_uid,
            Paragraph(c.company_name[:35], styles["Body"]),
            c.stage.value,
            c.status.value,
            c.invoice_status.value,
            c.rm.name if c.rm else "—",
            c.created_at.date().isoformat() if c.created_at else "—",
        ])
    elements.append(_data_table(
        headers, rows,
        col_widths=[2 * cm, 4.5 * cm, 3.2 * cm, 2.5 * cm, 2.3 * cm, 2.8 * cm, 2.2 * cm],
    ))
    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def compliance_calendar_pdf(dashboard: dict) -> bytes:
    buf = BytesIO()
    doc = _new_doc(buf)
    styles = _styles()
    elements = []
    elements += _brand_header(
        styles, "Compliance Calendar Report",
        f"Upcoming renewals, compliance filings & tax filings · {date.today().isoformat()}",
    )

    headers = ["Case", "Company", "Item", "Due Date", "Days Left"]
    rows = [
        [c["case_uid"], c["company_name"], c["item"].replace("_", " ").title(), c["due_date"].isoformat(), str(c["days_remaining"])]
        for c in dashboard["upcoming_compliance"]
    ]
    elements.append(_data_table(
        headers, rows,
        col_widths=[2.5 * cm, 5.5 * cm, 4 * cm, 2.5 * cm, 2.5 * cm],
    ))
    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def rm_ops_performance_pdf(dashboard: dict) -> bytes:
    buf = BytesIO()
    doc = _new_doc(buf)
    styles = _styles()
    elements = []
    elements += _brand_header(
        styles, "RM / Ops Performance Report",
        f"Caseload by Relationship Manager & Ops · {date.today().isoformat()}",
    )

    headers = ["Name", "Role", "Total Cases", "Active Cases"]
    rows = [
        [r["name"], r["role"].upper(), str(r["total_cases"]), str(r["active_cases"])]
        for r in dashboard["rm_ops_performance"]
    ]
    elements.append(_data_table(
        headers, rows,
        col_widths=[6 * cm, 3 * cm, 4 * cm, 4 * cm],
    ))
    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
