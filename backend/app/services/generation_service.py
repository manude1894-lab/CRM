"""Service layer: templated document generation.

Renders a branded PDF from a code-defined template, filling it from the case, and
saves it straight into the case document store as a Document (generated_from = code).
"""
from datetime import date

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Document, Case, User, UserRole
from app.reports import letter_pdf, resolution_pdf
from app.services import company_service, party_service
from app import jurisdictions

SIGNATORY_NAME = "Kalyanaram Sivalanka"
SIGNATORY_TITLE = "Director"


# ─── Context ────────────────────────────────────────────────────────────
def _get_case_for_write(db: Session, case_id: int, user: User) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if user.role == UserRole.RM and case.rm_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return case


def build_context(db: Session, case_id: int) -> dict:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    profile = company_service.get_or_create(db, case_id)
    directors = party_service.list_directors(db, case_id)
    shareholders = party_service.list_shareholders(db, case_id)
    ubos = party_service.list_ubos(db, case_id)
    top_ubo = max(
        (u for u in ubos if u.cessation_date is None),
        key=lambda u: float(u.percentage_interest or 0),
        default=None,
    )
    return {
        "case": case, "profile": profile, "directors": directors,
        "shareholders": shareholders, "ubos": ubos, "top_ubo": top_ubo,
        "spec": jurisdictions.get(case.jurisdiction),
    }


def _ra(ctx: dict) -> str:
    return (ctx["profile"].registered_agent or "").strip() or "Vistra (BVI) Limited"


def _company_number(ctx: dict) -> str | None:
    return ctx["profile"].company_number


def _director_names(ctx: dict) -> list[str]:
    names = []
    for d in ctx["directors"]:
        if d.cessation_date:
            continue
        if d.director_type == "Corporate":
            if d.corporate_name:
                names.append(d.corporate_name)
        else:
            full = " ".join(p for p in (d.first_name, d.middle_name, d.last_name) if p)
            if full:
                names.append(full)
    return names


def _ubo_name(ctx: dict) -> str:
    u = ctx["top_ubo"]
    return u.full_name if u else ""


def _fname(prefix: str, ctx: dict) -> str:
    return f"{prefix}_{ctx['case'].case_uid}_{date.today().isoformat()}.pdf"


# ─── Templates ──────────────────────────────────────────────────────────
def _b_reference_letter(p: dict, ctx: dict):
    subject = p.get("subject_name") or _ubo_name(ctx)
    years = p.get("years_known") or "over three (3)"
    context = p.get("relationship_context") or (
        f"{subject} has been known to this firm for {years} years. Throughout that period "
        f"{subject} has conducted their affairs with this firm in a proper and businesslike "
        "manner and, so far as we are aware, is a person of good financial standing and repute."
    )
    pdf = letter_pdf(
        recipient_lines=[p.get("addressed_to") or _ra(ctx), ctx["spec"].name],
        subject=f"{subject} — Character / Professional Reference",
        body_paragraphs=[
            f"We write in connection with the proposed onboarding of {subject} and the entity "
            f"{ctx['case'].company_name}.",
            context,
            "This reference is given in good faith and without any liability on the part of this "
            "firm or any of its officers or employees.",
        ],
        signatory_name=p.get("signatory_name") or SIGNATORY_NAME,
        signatory_title=p.get("signatory_title") or SIGNATORY_TITLE,
    )
    return pdf, _fname("Reference_Letter", ctx)


def _pf_reference_letter(ctx: dict) -> dict:
    return {
        "subject_name": _ubo_name(ctx),
        "years_known": "",
        "addressed_to": _ra(ctx),
        "relationship_context": "",
        "signatory_name": SIGNATORY_NAME,
        "signatory_title": SIGNATORY_TITLE,
    }


def _resolution(ctx: dict, heading: str, recitals: list[str], resolutions: list[str],
                prefix: str, res_date: str | None):
    d = None
    if res_date:
        try:
            d = date.fromisoformat(res_date)
        except ValueError:
            d = None
    pdf = resolution_pdf(
        company_name=ctx["case"].company_name,
        company_number=_company_number(ctx),
        heading=heading, recitals=recitals, resolutions=resolutions,
        signatories=_director_names(ctx), resolution_date=d,
        jurisdiction_name=ctx["spec"].name,
    )
    return pdf, _fname(prefix, ctx)


def _b_rora(p: dict, ctx: dict):
    s = ctx["spec"]
    ra = p.get("registered_agent") or _ra(ctx)
    office = p.get("registered_office") or f"the offices of {ra}, {s.name}"
    eff = p.get("effective_date") or date.today().isoformat()
    return _resolution(
        ctx, "Written Resolutions of the Directors — Registered Agent and Registered Office",
        ["The directors wish to confirm the Company's registered agent and registered office."],
        [f"{ra} be and is hereby confirmed as the registered agent of the Company with effect from {eff}.",
         f"The registered office of the Company be situated at {office}.",
         f"The registered agent be authorised to file this resolution and any related notice with the {s.registry_name}."],
        "Resolution_RA_RO", p.get("effective_date"))


def _pf_rora(ctx: dict) -> dict:
    ra = _ra(ctx)
    return {"registered_agent": ra,
            "registered_office": f"the offices of {ra}, {ctx['spec'].name}",
            "effective_date": date.today().isoformat()}


def _b_carrying_business(p: dict, ctx: dict):
    s = ctx["spec"]
    activity = p.get("business_activity") or (ctx["profile"].nature_of_business or "investment holding")
    return _resolution(
        ctx, "Written Resolutions of the Directors — Carrying on Business",
        ["The directors have reviewed the affairs of the Company."],
        [f"The directors confirm that the Company is carrying on the business of {activity} and is not dormant.",
         "The Company shall continue to maintain adequate accounting records and to meet its economic "
         f"substance and filing obligations under {s.law_short}."],
        "Resolution_Carrying_Business", p.get("effective_date"))


def _pf_carrying_business(ctx: dict) -> dict:
    return {"business_activity": ctx["profile"].nature_of_business or "",
            "effective_date": date.today().isoformat()}


def _b_record_keeping(p: dict, ctx: dict):
    s = ctx["spec"]
    loc = p.get("records_location") or f"the offices of {_ra(ctx)}, {s.name}"
    keeper = p.get("record_keeper") or _ra(ctx)
    return _resolution(
        ctx, "Written Resolutions of the Directors — Records and Record Keeping",
        ["The directors wish to confirm the arrangements for keeping the Company's records."],
        [f"The records and underlying documentation of the Company be kept at {loc}.",
         f"{keeper} be and is hereby authorised to hold the Company's records and to provide them to "
         f"the competent authority on request in accordance with {s.law_short}.",
         "The registered agent be notified in writing of the physical address at which the records are kept."],
        "Resolution_Record_Keeping", p.get("effective_date"))


def _pf_record_keeping(ctx: dict) -> dict:
    ra = _ra(ctx)
    return {"records_location": f"the offices of {ra}, {ctx['spec'].name}",
            "record_keeper": ra, "effective_date": date.today().isoformat()}


def _b_change_director(p: dict, ctx: dict):
    s = ctx["spec"]
    name = p.get("director_name") or ""
    action = (p.get("action") or "Appointed").lower()
    eff = p.get("effective_date") or date.today().isoformat()
    return _resolution(
        ctx, "Written Resolutions of the Directors — Change of Director",
        ["The directors wish to record a change to the board of the Company."],
        [f"{name} be and is hereby {action} as a director of the Company with effect from {eff}.",
         f"The Register of Directors be updated accordingly and the change filed with the {s.registry_name} "
         f"within the period prescribed by the {s.company_law_name}.",
         "The registered agent be instructed to effect the above filing."],
        "Resolution_Change_Director", p.get("effective_date"))


def _pf_change_director(ctx: dict) -> dict:
    return {"director_name": "", "action": "Appointed", "effective_date": date.today().isoformat()}


def _b_first_board(p: dict, ctx: dict):
    s = ctx["spec"]
    ra = p.get("registered_agent") or _ra(ctx)
    directors = ", ".join(_director_names(ctx)) or "the first director(s) named in the incorporation application"
    return _resolution(
        ctx, "Written Resolutions of the First Director(s) — Incorporation Matters",
        ["The following resolutions are adopted by the first director(s) of the Company on incorporation."],
        [f"The Memorandum and Articles of Association of the Company be and are hereby adopted.",
         f"{directors} be and is/are confirmed as the first director(s) of the Company.",
         "The initial shares of the Company be allotted and issued as set out in the Register of Members, "
         "and the corresponding share certificate(s) be issued.",
         f"{ra} be and is hereby appointed as the registered agent of the Company and its offices as the "
         "registered office of the Company.",
         f"The registered agent be authorised to file the Register of Directors with the {s.registry_name} "
         f"within {s.rod_filing_days} days of the appointment of the first director(s)."],
        "Resolution_First_Board", p.get("meeting_date"))


def _pf_first_board(ctx: dict) -> dict:
    return {"registered_agent": _ra(ctx), "meeting_date": date.today().isoformat()}


def _b_change_shareholding(p: dict, ctx: dict):
    transferor = p.get("transferor") or ""
    transferee = p.get("transferee") or ""
    shares = p.get("number_of_shares") or ""
    cls = p.get("share_class") or "ordinary"
    eff = p.get("effective_date") or date.today().isoformat()
    return _resolution(
        ctx, "Written Resolutions of the Directors — Change of Shareholding",
        ["The directors wish to record a transfer of shares in the Company."],
        [f"The transfer of {shares} {cls} share(s) from {transferor} to {transferee} with effect from "
         f"{eff} be and is hereby approved.",
         "The Register of Members be updated and a new share certificate issued to the transferee.",
         "The beneficial ownership position be reviewed and any ROM / RBO filing made within the "
         "prescribed period."],
        "Resolution_Change_Shareholding", p.get("effective_date"))


def _pf_change_shareholding(ctx: dict) -> dict:
    return {"transferor": "", "transferee": "", "number_of_shares": "", "share_class": "ordinary",
            "effective_date": date.today().isoformat()}


def _b_vistra_cover(p: dict, ctx: dict):
    enclosures = (p.get("enclosures") or "").strip()
    body = [
        p.get("request_body") or "Please find enclosed the following instruction for your action.",
    ]
    if enclosures:
        body.append(f"Enclosures: {enclosures}")
    body.append("We should be grateful if you would action the above at your earliest convenience. "
                "Please do not hesitate to contact us should you require any further information.")
    pdf = letter_pdf(
        recipient_lines=[p.get("addressed_to") or _ra(ctx), ctx["spec"].name],
        subject=p.get("re_subject") or f"{ctx['case'].company_name} — Service Request",
        body_paragraphs=body,
        signatory_name=p.get("signatory_name") or SIGNATORY_NAME,
        signatory_title=p.get("signatory_title") or SIGNATORY_TITLE,
    )
    return pdf, _fname("Cover_Letter", ctx)


def _pf_vistra_cover(ctx: dict) -> dict:
    return {"addressed_to": _ra(ctx),
            "re_subject": f"{ctx['case'].company_name} — Service Request",
            "request_body": "", "enclosures": "",
            "signatory_name": SIGNATORY_NAME, "signatory_title": SIGNATORY_TITLE}


_TXT = "text"
_TA = "textarea"
_DT = "date"

TEMPLATE_CATALOG = [
    {
        "code": "reference_letter", "label": "Reference Letter (to Registered Agent)",
        "category": "Reference Letter", "builder": _b_reference_letter, "prefill": _pf_reference_letter,
        "fields": [
            {"key": "subject_name", "label": "Individual", "type": _TXT, "required": True},
            {"key": "years_known", "label": "Years known", "type": _TXT},
            {"key": "addressed_to", "label": "Addressed to", "type": _TXT},
            {"key": "relationship_context", "label": "Reference wording (leave blank for the standard text)", "type": _TA},
            {"key": "signatory_name", "label": "Signatory name", "type": _TXT},
            {"key": "signatory_title", "label": "Signatory title", "type": _TXT},
        ],
    },
    {
        "code": "resolution_rora", "label": "Resolution — Registered Agent & Office",
        "category": "Corporate Document", "builder": _b_rora, "prefill": _pf_rora,
        "fields": [
            {"key": "registered_agent", "label": "Registered agent", "type": _TXT},
            {"key": "registered_office", "label": "Registered office", "type": _TXT},
            {"key": "effective_date", "label": "Effective date", "type": _DT},
        ],
    },
    {
        "code": "resolution_carrying_business", "label": "Resolution — Carrying on Business",
        "category": "Corporate Document", "builder": _b_carrying_business, "prefill": _pf_carrying_business,
        "fields": [
            {"key": "business_activity", "label": "Business activity", "type": _TXT},
            {"key": "effective_date", "label": "Resolution date", "type": _DT},
        ],
    },
    {
        "code": "resolution_record_keeping", "label": "Resolution — Records & Record Keeping",
        "category": "Corporate Document", "builder": _b_record_keeping, "prefill": _pf_record_keeping,
        "fields": [
            {"key": "records_location", "label": "Records location", "type": _TXT},
            {"key": "record_keeper", "label": "Record keeper", "type": _TXT},
            {"key": "effective_date", "label": "Resolution date", "type": _DT},
        ],
    },
    {
        "code": "resolution_first_board", "label": "Resolution — First Board / Incorporation",
        "category": "Corporate Document", "builder": _b_first_board, "prefill": _pf_first_board,
        "fields": [
            {"key": "registered_agent", "label": "Registered agent", "type": _TXT},
            {"key": "meeting_date", "label": "Meeting date", "type": _DT},
        ],
    },
    {
        "code": "resolution_change_director", "label": "Resolution — Change of Director",
        "category": "Corporate Document", "builder": _b_change_director, "prefill": _pf_change_director,
        "fields": [
            {"key": "director_name", "label": "Director", "type": _TXT, "required": True},
            {"key": "action", "label": "Action", "type": "select", "required": True,
             "options": ["Appointed", "Resigned"]},
            {"key": "effective_date", "label": "Effective date", "type": _DT, "required": True},
        ],
    },
    {
        "code": "resolution_change_shareholding", "label": "Resolution — Change of Shareholding",
        "category": "Corporate Document", "builder": _b_change_shareholding, "prefill": _pf_change_shareholding,
        "fields": [
            {"key": "transferor", "label": "Transferor", "type": _TXT, "required": True},
            {"key": "transferee", "label": "Transferee", "type": _TXT, "required": True},
            {"key": "number_of_shares", "label": "Number of shares", "type": _TXT},
            {"key": "share_class", "label": "Share class", "type": _TXT},
            {"key": "effective_date", "label": "Effective date", "type": _DT, "required": True},
        ],
    },
    {
        "code": "vistra_cover_letter", "label": "Cover Letter to Registered Agent",
        "category": "Corporate Document", "builder": _b_vistra_cover, "prefill": _pf_vistra_cover,
        "fields": [
            {"key": "addressed_to", "label": "Addressed to", "type": _TXT},
            {"key": "re_subject", "label": "RE subject", "type": _TXT, "required": True},
            {"key": "request_body", "label": "Request", "type": _TA, "required": True},
            {"key": "enclosures", "label": "Enclosures", "type": _TA},
            {"key": "signatory_name", "label": "Signatory name", "type": _TXT},
            {"key": "signatory_title", "label": "Signatory title", "type": _TXT},
        ],
    },
]

_BY_CODE = {t["code"]: t for t in TEMPLATE_CATALOG}


def list_templates() -> list[dict]:
    return [
        {"code": t["code"], "label": t["label"], "category": t["category"], "fields": t["fields"]}
        for t in TEMPLATE_CATALOG
    ]


def _template(code: str) -> dict:
    t = _BY_CODE.get(code)
    if not t:
        raise HTTPException(status_code=400, detail=f"Unknown document template: {code}")
    return t


def prefill(db: Session, case_id: int, code: str, user: User) -> dict:
    _get_case_for_write(db, case_id, user)
    t = _template(code)
    return t["prefill"](build_context(db, case_id))


def generate(db: Session, case_id: int, code: str, params: dict, user: User) -> Document:
    _get_case_for_write(db, case_id, user)
    t = _template(code)
    ctx = build_context(db, case_id)
    merged = {**t["prefill"](ctx), **(params or {})}
    pdf_bytes, filename = t["builder"](merged, ctx)
    doc = Document(
        case_id=case_id,
        category=t["category"],
        filename=filename,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
        content=pdf_bytes,
        uploaded_by_id=user.id,
        generated_from=code,
        notes=f"Generated from template '{t['label']}' on {date.today().isoformat()}",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc
