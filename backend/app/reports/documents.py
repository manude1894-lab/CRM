"""Formal document PDFs — letters and board resolutions.

Reuses the ReportLab plumbing in app.reports.pdf (styles, page frame, brand
colours). These are Triam's own outgoing documents, not internal reports.
"""
from io import BytesIO
from datetime import date

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app.reports.pdf import _styles, _new_doc, _header_footer, PRIMARY, MUTED, DARK

FIRM_NAME = "TRIAM Management Services FZCO"
FIRM_ADDRESS = "Dubai Silicon Oasis, Dubai, United Arab Emirates"


def _p(text, style):
    return Paragraph(text.replace("\n", "<br/>"), style)


def _letterhead(styles):
    return [
        _p(f"<b>{FIRM_NAME}</b>", styles["BrandSub"]),
        _p(FIRM_ADDRESS, styles["BrandSub"]),
        Spacer(1, 0.6 * cm),
    ]


def _signature_block(styles, name: str, title: str):
    return [
        Spacer(1, 1.2 * cm),
        _p("Yours faithfully,", styles["Body"]),
        Spacer(1, 1.0 * cm),
        _p(f"<b>{name}</b>", styles["Body"]),
        _p(title, styles["Body"]),
        _p(f"for and on behalf of {FIRM_NAME}", styles["Body"]),
    ]


def letter_pdf(*, recipient_lines: list[str], subject: str, body_paragraphs: list[str],
               signatory_name: str, signatory_title: str, letter_date: date | None = None) -> bytes:
    buf = BytesIO()
    doc = _new_doc(buf)
    styles = _styles()
    el = _letterhead(styles)
    el.append(_p((letter_date or date.today()).strftime("%d %B %Y"), styles["Body"]))
    el.append(Spacer(1, 0.5 * cm))
    for line in recipient_lines:
        el.append(_p(line, styles["Body"]))
    el.append(Spacer(1, 0.5 * cm))
    el.append(_p("Dear Sirs,", styles["Body"]))
    el.append(Spacer(1, 0.3 * cm))
    if subject:
        el.append(_p(f"<b>RE: {subject}</b>", styles["Body"]))
        el.append(Spacer(1, 0.3 * cm))
    for para in body_paragraphs:
        el.append(_p(para, styles["Body"]))
        el.append(Spacer(1, 0.25 * cm))
    el += _signature_block(styles, signatory_name, signatory_title)
    doc.build(el, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def resolution_pdf(*, company_name: str, company_number: str | None, heading: str,
                   recitals: list[str], resolutions: list[str], signatories: list[str],
                   resolution_date: date | None = None, jurisdiction_name: str = "British Virgin Islands") -> bytes:
    buf = BytesIO()
    doc = _new_doc(buf)
    styles = _styles()
    el = [
        _p(f"<b>{company_name}</b>", styles["BrandTitle"]),
        _p(f"({jurisdiction_name} Company Number: {company_number})" if company_number else f"({jurisdiction_name})", styles["BrandSub"]),
        Spacer(1, 0.4 * cm),
        _p(f"<b>{heading.upper()}</b>", styles["H2"]),
        _p((resolution_date or date.today()).strftime("%d %B %Y"), styles["Body"]),
        Spacer(1, 0.4 * cm),
    ]
    for r in recitals:
        el.append(_p(r, styles["Body"]))
        el.append(Spacer(1, 0.2 * cm))
    el.append(Spacer(1, 0.2 * cm))
    el.append(_p("<b>IT WAS RESOLVED THAT:</b>", styles["Body"]))
    el.append(Spacer(1, 0.2 * cm))
    for i, r in enumerate(resolutions, 1):
        el.append(_p(f"{i}. {r}", styles["Body"]))
        el.append(Spacer(1, 0.2 * cm))
    el.append(Spacer(1, 1.0 * cm))
    el.append(_p("Signed by the director(s):", styles["Body"]))
    for name in signatories or ["_______________________________"]:
        el.append(Spacer(1, 0.9 * cm))
        el.append(_p("_______________________________", styles["Body"]))
        el.append(_p(name, styles["Body"]))
    doc.build(el, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
