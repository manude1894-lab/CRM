"""Builds the Triam CRM data dictionary (Excel) from the code: every field the users enter, with its screen label,
stored name, data type and length, when it is mandatory, the allowed values and the checks applied.

Triam UAT 25-11-2026 row 204: "Provide meta data of the UAT CRM, with field names, data characteristics,
constraints etc." Run from the repository root after a change to the fields:

    backend/.venv/Scripts/python.exe scripts/data_dictionary.py docs/Triam_CRM_Data_Dictionary.xlsx
"""
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402

from app import models  # noqa: E402
from app.services import client_workflow_service as wf  # noqa: E402

FRONT = ROOT / "frontend" / "src"
BRAND = "1A3A5C"

# ── screen labels, read from the forms ─────────────────────────────────────────


def labels_from(*files) -> dict:
    """field -> label, from <Field label="..."> followed by the field it edits."""
    out = {}
    for f in files:
        text = (FRONT / f).read_text(encoding="utf-8")
        for m in re.finditer(r'<(?:Field|YesNo)\s+label=\{?"([^"]+)"', text):
            tail = text[m.end(): m.end() + 400]
            hit = re.search(r'(?:req|miss|set|setValue|setChecked)\("([a-z_]+)"\)|form\.([a-z_]+)', tail)
            if hit:
                field = hit.group(1) or hit.group(2)
                out.setdefault(field, m.group(1))
    return out


# ── what each field must satisfy (from the validation code) ───────────────────

ALWAYS, AT_SUBMIT, COMPLIANCE = "Always", "At Submit for approval", "At Compliance approval"
NOT_FORMING = "At Submit, unless Under Formation"
INDIVIDUAL = "At Submit, Individual clients"
COMPANY = "At Submit, company clients"
FUTURE_NO = "Not in the future"

CLIENT = {
    # field: (mandatory, allowed values, checks)
    "anchor_entity": (AT_SUBMIT, "Master list: Triam entities", "Not also a Non-anchor entity"),
    "non_anchor_entities": ("No", "Master list: Triam entities", "Several allowed; not the Anchor entity"),
    "spoc_id": (AT_SUBMIT, "Active users who handle clients", ""),
    "non_anchor_rm_ids": ("No", "Active users who handle clients", "Several allowed; not the Anchor RM"),
    "account_type": (ALWAYS, "Corporate / Individual (and other client types)", ""),
    "company_name": (ALWAYS, "", "Unique among clients (case and spacing ignored); at most 255 characters"),
    "search_name": (AT_SUBMIT, "", "Unique; made from the name and entity when left blank"),
    "client_category": (COMPANY, "Under Formation / Existing", ""),
    "country": (COMPANY, "Country list", ""),
    "contact_mobile_country_code": (COMPANY, "Dialling codes", ""),
    "contact_mobile_number": (COMPANY, "", "Digits only; UAE (+971) 9 digits (mobile) or 8 (landline); India, USA / Canada 10; UK, Pakistan, Philippines, Egypt 9 to 10; Saudi Arabia 8 to 9; Qatar, Bahrain, Kuwait, Oman, Singapore, Hong Kong 8; any other country 8 to 12"),
    "contact_email": (COMPANY, "", "A valid email address"),
    "is_one_time_service": (COMPANY + ", when the services asked need it", "Yes / No", ""),
    "nature_of_services_sought": (AT_SUBMIT, "Master list: services (those offered by the chosen entities)", "At least one"),
    "registration_number": (NOT_FORMING, "", "At most 30 characters"),
    "incorporation_date": (NOT_FORMING, "", FUTURE_NO),
    "license_number": (NOT_FORMING, "", "At most 30 characters"),
    "licensing_authority": (COMPANY, "Master list: registering authorities, or Other", ""),
    "licensing_authority_other": ("When Registering Authority is Other", "", ""),
    "license_activities": (NOT_FORMING, "", ""),
    "license_start_date": (NOT_FORMING, "", "Not in the future; not before the Incorporation Date (checked again at Submit)"),
    "license_expiry_date": (NOT_FORMING, "", "Not before today when entered; after the Licence Start Date; an expired licence blocks Submit"),
    "is_regulated": (COMPANY, "Yes / No", ""),
    "regulator_name": ("When regulated", "Master list: regulators, or Other", ""),
    "regulator_other": ("When Regulator is Other", "", ""),
    "license_category": ("When regulated", "", "At most 25 characters"),
    "regulatory_license_expiry_date": ("When regulated", "", "Not before today when entered"),
    "lei_number": ("No", "", "Up to 20 letters and digits"),
    "lei_expiry_date": ("No", "", "Not before today when entered"),
    "registered_address": (COMPANY, "", "Line 1, City and Country required"),
    "operating_address": (COMPANY, "", "Line 1, City and Country required; can copy the Registered Address"),
    "trn_vat_number": ("No", "", "Letters and digits only, no spaces; a UAE number is 15 digits"),
    "corp_tax_registered": ("At Submit, when taxable (not offshore)", "Yes / No", ""),
    "corp_tax_registration_number": ("When Corporate Tax Registered is Yes", "", "Letters and digits only; a UAE number is 15 digits"),
    "financial_year_end": ("At Submit, when taxable (not offshore)", "Day and month", "A valid day of the month"),
    "has_introducer": (AT_SUBMIT, "Yes / No", ""),
    "introducer_name": ("When there is an introducer", "", ""),
    "date_of_birth": (INDIVIDUAL, "", "Adult (18 or over); not in the future"),
    "country_of_birth": (INDIVIDUAL, "Country list", ""),
    "nationality": (INDIVIDUAL, "Country list", ""),
    "passport_number": (INDIVIDUAL, "", "Letters and digits only (spaces and dashes dropped), length within the passport range"),
    "passport_expiry_date": (INDIVIDUAL, "", "After the date of birth; not expired"),
    "country_of_residence": (INDIVIDUAL, "Country list", ""),
    "residential_address": (INDIVIDUAL, "", "Line 1, City and Country required"),
    "individual_mobile_country_code": (INDIVIDUAL, "Dialling codes", ""),
    "individual_mobile_number": (INDIVIDUAL, "", "Digits only; UAE (+971) 9 digits (mobile) or 8 (landline); India, USA / Canada 10; UK, Pakistan, Philippines, Egypt 9 to 10; Saudi Arabia 8 to 9; Qatar, Bahrain, Kuwait, Oman, Singapore, Hong Kong 8; any other country 8 to 12"),
    "individual_email": (INDIVIDUAL, "", "A valid email address"),
    "uae_visa_number": ("No", "", ""),
    "uae_visa_expiry": ("No", "", "Not expired more than 30 days ago when entered"),
    "is_pep": ("No", "Yes / No", "Set automatically when a person on the client is a PEP"),
    "tags": ("No", "Master list: client tags", "Several allowed"),
    "screening_date": ("No", "", FUTURE_NO),
    "br_person_met": (AT_SUBMIT, "", "At most 255 characters"),
    "br_meeting_place": (AT_SUBMIT, "", "At most 255 characters"),
    "br_meeting_date": (AT_SUBMIT, "", FUTURE_NO),
    "br_meeting_time": (AT_SUBMIT, "", "HH:MM; for a meeting today, not later than now"),
    "br_meeting_mode": (AT_SUBMIT, "Master list: meeting modes", ""),
    "br_rationale": (AT_SUBMIT, "", ""),
    "engagement_letter_signed": (AT_SUBMIT, "Yes / No", ""),
    "engagement_letter_valid_until": ("When the engagement letter is signed", "", "Not before today when entered"),
    "risk_rating": (COMPLIANCE, "High / Medium / Low", "Sets the next AML review date"),
    "edd_reason": ("At Compliance approval, when risk is High", "", "Up to 250 characters"),
    "kyc_verified_by": (COMPLIANCE, "", ""),
    "cdd_completion_date": (COMPLIANCE, "", FUTURE_NO),
    "next_aml_review_date": ("Set by the CRM", "", "From the risk level and the CDD completion date"),
    "profile_status": ("Set by the workflow", ", ".join(wf.CLIENT_STATUSES) if hasattr(wf, "CLIENT_STATUSES") else "See the workflow", ""),
    "status_reason_code": ("With Drop / Mark for Exit", "Drop reasons; exit reasons", ""),
    "status_reason": ("With Mark for Exit", "", "Comments, up to 250 characters for an exit"),
    "client_id": ("Set by the CRM", "", "Issued at the Final approval (which also makes the client Active): <entity>/<number>; never changes"),
    "onboarding_invoice_wanted": ("No", "Yes / No", ""),
}

PARTY = {
    "party_role": (ALWAYS, "Shareholder, Director, Authorised Signatory, Joint Holder, Founder, Council Member, Beneficiary, Guardian", ""),
    "constitution": (ALWAYS, "Individual / Entity", ""),
    "full_name": (ALWAYS, "", "At most 255 characters"),
    "dob_or_incorp_date": (AT_SUBMIT, "", "Not in the future; an individual's passport expires after it"),
    "id_or_license_expiry": (AT_SUBMIT, "", "An individual's passport: after the date of birth, not expired"),
    "passport_number": (AT_SUBMIT + " (individuals)", "", "Letters and digits only, length within the passport range"),
    "nationality": ("Always, individuals", "Country list", ""),
    "country_of_incorp_or_birth": ("Always for entities; for individuals when needed", "Country list", ""),
    "country_of_residence": (ALWAYS, "Country list", ""),
    "residential_address": (AT_SUBMIT, "", "Line 1 and City required"),
    "mobile_country_code": ("With a mobile number", "Dialling codes", ""),
    "mobile_number": ("No", "", "Digits only; UAE (+971) 9 digits (mobile) or 8 (landline); India, USA / Canada 10; UK, Pakistan, Philippines, Egypt 9 to 10; Saudi Arabia 8 to 9; Qatar, Bahrain, Kuwait, Oman, Singapore, Hong Kong 8; any other country 8 to 12"),
    "email": ("No", "", "A valid email address"),
    "uae_visa_number": ("No", "", ""),
    "uae_visa_expiry": ("No", "", "Not expired more than 30 days ago when entered"),
    "is_pep": ("No", "Yes / No", "Makes the client a PEP"),
    "effective_ownership_percent": ("Shareholders (individuals)", "", "0 to 100, 2 decimals; individual shareholders total 100% at Submit; none for entities"),
    "nominee_director_name": ("No", "", ""),
    "guardian_name": ("When the person is a minor", "", "At most 255 characters"),
    "guardian_relationship": ("When the person is a minor", "", "At most 60 characters"),
    "notes": ("No", "", ""),
}

PROSPECT = {
    "company_name": (ALWAYS, "", "A possible duplicate is shown while typing"),
    "contact_name": ("No", "", ""),
    "contact_email": ("No", "", "A valid email address"),
    "contact_phone": ("No", "", "Digits only, with the country code"),
    "source": ("No", "Master list: prospect sources, or Other", ""),
    "owner_id": ("No", "Relationship managers", "Set when the prospect is assigned"),
    "status": (ALWAYS, "New / Won / Dropped", ""),
    "notes": ("No", "", ""),
}

ACTIVITY = {
    "account_id": (ALWAYS, "Clients the user may see", ""),
    "activity_type": (ALWAYS, "Visit Report / Call Report", ""),
    "activity_date": (ALWAYS, "", "Not more than 7 days back when entered"),
    "client_contact": ("Save the Report", "", "At most 150 characters"),
    "location": ("Save the Report, Visit Reports", "", "At most 200 characters"),
    "attendees": ("No", "", ""),
    "purpose": ("No", "", "At most 200 characters"),
    "summary": ("Save the Report", "", "Discussion points"),
    "outcome": ("No", "", ""),
    "next_action": ("No", "", ""),
    "due_date": ("No", "", "Not in the past"),
    "status": ("Set by the CRM", "Draft / Completed (final) / Cancelled", "A final report is kept as written; corrections are notes"),
}

INSTRUCTION = {
    "account_id": (ALWAYS, "Clients approved by Compliance, served by the entity", ""),
    "triam_entity": (ALWAYS, "Master list: Triam entities", ""),
    "instruction_type": (ALWAYS, "Master list: service request types (per entity)", ""),
    "other_description": ("When the type is Other", "", "Up to 50 characters"),
    "status": (ALWAYS, "Master list: statuses (per entity)", ""),
    "date_received": ("No", "", ""),
    "date_completed": ("No", "", ""),
    "charge_amount": ("No", "", "Amount and currency"),
    "comments": ("No", "", ""),
}

INVOICE = {
    "account_id": (ALWAYS, "Clients the user may see", ""),
    "kind": ("Set by the CRM", "Onboarding / Service Request", ""),
    "description": (ALWAYS, "", "2 to 500 characters"),
    "amount": (ALWAYS, "", "0 or more, 2 decimals"),
    "currency": (ALWAYS, "AED, USD, EUR, GBP, INR, SGD", ""),
    "status": ("Set by the CRM", "Draft, With Compliance, Requested, Raised, Paid, Overdue, Cancelled", ""),
    "invoice_number": ("When Accounts raises it", "", "At most 50 characters; the invoice file must be attached"),
    "raised_date": ("When Accounts raises it", "", ""),
    "due_date": ("No", "", ""),
    "paid_date": ("When marked paid", "", ""),
    "notes": ("No", "", ""),
    "govt_authority_amount": ("No", "", "Onboarding invoices"),
    "introducer_involved": ("Onboarding invoices, to send", "Yes / No", ""),
    "introducer_amount": ("When an introducer is involved", "", ""),
    "co_comment": ("When Compliance returns it", "", "Up to 500 characters"),
}

USER = {
    "name": (ALWAYS, "", ""),
    "email": (ALWAYS, "", "Unique; the sign-in name"),
    "role": (ALWAYS, "Administrator / user", ""),
    "business_role_id": ("No", "Admin: roles", "Decides the permissions"),
    "department_id": ("No", "Admin: departments", ""),
    "supervisor_id": ("No", "Users", "Sees the team's clients"),
    "title": ("No", "", ""),
    "mobile": ("No", "", ""),
    "is_active": (ALWAYS, "Active / Inactive", "Users are deactivated, not deleted"),
    "can_export_reports": ("No", "Yes / No", "May download reports as Excel / PDF"),
}


# Labels that change with the client type on screen (so the form code doesn't give them as plain text).
LABELS = {
    "Clients": {
        "company_name": "Client Name (company) / Full Name (individual)", "search_name": "Unique Search Name",
        "non_anchor_rm_ids": "Non-anchor RMs", "country": "Country of Incorporation / Registration",
        "contact_mobile_country_code": "Contact Mobile (country code)", "contact_email": "Contact Email",
        "nature_of_services_sought": "Nature of Services sought", "incorporation_date": "Incorporation Date",
        "license_number": "Trade / Commercial License Number", "license_start_date": "License Start / Registration Date",
        "license_expiry_date": "License Expiry Date", "license_category": "License Category", "lei_expiry_date": "LEI Expiry Date",
        "registered_address": "Registered Address", "operating_address": "Operating Address", "financial_year_end": "Financial Year End",
        "introducer_name": "Introducer Name", "date_of_birth": "Date of Birth", "country_of_birth": "Country of Birth",
        "nationality": "Nationality", "passport_number": "Passport Number", "passport_expiry_date": "Passport Expiry Date",
        "country_of_residence": "Country of Residence", "residential_address": "Residential Address",
        "individual_mobile_country_code": "Contact Mobile (country code)", "uae_visa_expiry": "UAE Visa Expiry",
        "is_pep": "Politically Exposed Person (PEP)", "tags": "Tags", "screening_date": "Screening Date",
        "engagement_letter_signed": "Engagement Letter Signed", "engagement_letter_valid_until": "Engagement Letter Valid Until",
        "cdd_completion_date": "CDD Completion Date", "next_aml_review_date": "Next AML Review Date", "profile_status": "Status",
        "status_reason_code": "Status reason", "status_reason": "Status comments", "client_id": "Client ID",
        "onboarding_invoice_wanted": "Do you want an invoice raised for onboarding services?",
    },
    "People": {
        "constitution": "Individual / Entity", "full_name": "Full Name", "dob_or_incorp_date": "Date of Birth / Incorporation",
        "id_or_license_expiry": "Passport / Licence Expiry", "passport_number": "Passport Number", "nationality": "Nationality",
        "country_of_incorp_or_birth": "Country of Birth / Incorporation", "country_of_residence": "Country of Residence",
        "mobile_number": "Mobile", "uae_visa_expiry": "UAE Visa Expiry", "is_pep": "PEP", "notes": "Notes",
    },
    "Prospects": {"contact_name": "Contact Name", "contact_email": "Contact Email", "contact_phone": "Contact Phone",
                  "source": "Source", "status": "Status"},
    "Visit & Call Reports": {"client_contact": "Client contact met / spoken to", "location": "Location", "purpose": "Purpose",
                             "outcome": "Outcome", "next_action": "Next action", "status": "Draft / Final"},
    "Service Requests": {"triam_entity": "Triam Entity", "date_received": "Date Received", "date_completed": "Date Completed",
                         "charge_amount": "Charge", "comments": "Comments"},
    "Invoices": {"kind": "Invoice for", "description": "Description", "amount": "Amount", "currency": "Currency", "status": "Status",
                 "raised_date": "Invoice Date", "due_date": "Due Date", "paid_date": "Paid Date",
                 "govt_authority_amount": "Amount payable to the Regn / Govt Authority",
                 "introducer_involved": "Introducer / referrer involved?", "introducer_amount": "Amount payable to the introducer",
                 "co_comment": "Compliance comments"},
    "Users": {"email": "Email", "business_role_id": "Business Role", "department_id": "Department", "title": "Title",
              "can_export_reports": "Can download reports"},
}

SHEETS = [
    ("Clients", models.Account, CLIENT, ("components/accounts/AccountFormModal.jsx",)),
    ("People", models.AccountParty, PARTY, ("components/AccountPartyModal.jsx",)),
    ("Prospects", models.Prospect, PROSPECT, ("pages/ProspectsPage.jsx",)),
    ("Visit & Call Reports", models.Activity, ACTIVITY, ("components/activities/ActivityForm.jsx",)),
    ("Service Requests", models.Instruction, INSTRUCTION, ("pages/InstructionsPage.jsx",)),
    ("Invoices", models.Invoice, INVOICE, ("pages/InvoicesPage.jsx", "components/accounts/OnboardingInvoicePanel.jsx")),
    ("Users", models.User, USER, ("pages/AdminPage.jsx",)),
]


def data_type(col) -> tuple[str, str]:
    t = col.type
    if isinstance(t, Boolean):
        return "Yes / No", ""
    if isinstance(t, DateTime):
        return "Date and time", ""
    if isinstance(t, Date):
        return "Date (DD MM YYYY)", ""
    if isinstance(t, Numeric):
        return "Number", f"{t.precision} digits, {t.scale} decimals" if t.precision else ""
    if isinstance(t, Integer):
        return ("Reference" if col.foreign_keys else "Whole number"), ""
    if isinstance(t, JSONB) or t.__class__.__name__ in ("JSON", "JSONB"):
        return "Structured (list / address)", ""
    if isinstance(t, Text):
        return "Text (long)", ""
    if isinstance(t, String):
        enum = getattr(t, "enums", None)
        if enum:
            return "Choice", ""
        return "Text", f"{t.length} characters" if t.length else ""
    return t.__class__.__name__, ""


def humanize(name: str) -> str:
    return name.replace("_ids", "").replace("_id", "").replace("_", " ").capitalize()


def build(path: Path) -> None:
    wb = Workbook()
    intro = wb.active
    intro.title = "About"
    lines = [
        ("Triam CRM - Data dictionary", Font(bold=True, size=14)),
        (f"Generated from the CRM code on {date.today():%d %m %Y}", Font(italic=True, color="666666")),
        ("", None),
        ("One sheet per record type. For each field: the label on screen, the name stored in the database, the data type and", None),
        ("length, when it is mandatory, the allowed values and the checks the CRM applies.", None),
        ("", None),
        ("Mandatory: \"Always\" means it cannot be saved without it; \"At Submit\" means the client can be saved as a draft,", None),
        ("but cannot be submitted for approval until it is filled; \"At Compliance approval\" is filled by Compliance.", None),
        ("Master list: values the Administrator maintains under Admin > Master Data.", None),
        ("Fields set by the CRM itself (IDs, dates of changes, who did what) are listed at the end of each sheet in grey.", None),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        c = intro.cell(row=i, column=1, value=text)
        if font:
            c.font = font
    intro.column_dimensions["A"].width = 120

    thin = Side(style="thin", color="D9DEE5")
    border = Border(top=thin, bottom=thin, left=thin, right=thin)
    head = ["Screen label", "Field name", "Data type", "Length / precision", "Mandatory", "Allowed values", "Checks / rules", "Kind"]
    widths = [34, 30, 22, 18, 34, 44, 60, 12]
    for title, model, rules, forms in SHEETS:
        ws = wb.create_sheet(title)
        labels = labels_from(*forms)
        ws.append(head)
        for j, c in enumerate(ws[1], start=1):
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor=BRAND)
            c.alignment = Alignment(vertical="center", wrap_text=True)
            c.border = border
            ws.column_dimensions[get_column_letter(j)].width = widths[j - 1]
        cols = list(model.__table__.columns)
        entered = [c for c in cols if c.name in rules]
        system = [c for c in cols if c.name not in rules]
        order = list(rules)
        entered.sort(key=lambda c: order.index(c.name))
        for kind, group in (("Entered", entered), ("System", system)):
            for col in group:
                dtype, length = data_type(col)
                mand, allowed, checks = rules.get(col.name, ("Set by the CRM", "", ""))
                label = LABELS.get(title, {}).get(col.name) or labels.get(col.name) or humanize(col.name)
                if kind == "System" and col.name in ("id",):
                    label = "Internal ID"
                ws.append([label, col.name, dtype, length, mand, allowed, checks, kind])
                for c in ws[ws.max_row]:
                    c.alignment = Alignment(vertical="top", wrap_text=True)
                    c.border = border
                    if kind == "System":
                        c.font = Font(color="808080")
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = f"A1:H{ws.max_row}"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = "1:1"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print("written", path)


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "Triam_CRM_Data_Dictionary.xlsx"))
