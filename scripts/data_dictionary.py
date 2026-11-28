"""Builds the Triam CRM data dictionary (Excel): every field the users enter, with its screen label,
stored name, data type and length, when it is mandatory, the allowed values and the checks applied.

Triam UAT 25-11-2026 row 204: "Provide meta data of the UAT CRM, with field names, data characteristics,
constraints etc." Run from the repository root after a change to the fields:

    backend/.venv/Scripts/python.exe scripts/data_dictionary.py docs/Triam_CRM_Data_Dictionary.xlsx
"""
import json
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
PHONE = "Digits only; length as per the country code (see the Phone Number Lengths sheet)"

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
    "contact_mobile_number": (COMPANY, "", PHONE),
    "contact_email": (COMPANY, "", "A valid email address"),
    "single_point_of_contact": ("No", "", "Name of the contact person at the client"),
    "is_one_time_service": (COMPANY + ", when the services asked need it", "Yes / No", ""),
    "nature_of_services_sought": (AT_SUBMIT, "Master list: services (those offered by the chosen entities)", "At least one"),
    "registration_number": (NOT_FORMING, "", "At most 30 characters"),
    "incorporation_date": (NOT_FORMING, "", FUTURE_NO),
    "license_number": (NOT_FORMING, "", "At most 30 characters"),
    "licensing_authority": (COMPANY, "Master list: registering authorities, or Other", ""),
    "licensing_authority_other": ("When Registering Authority is Other", "", ""),
    "license_activities": (NOT_FORMING, "", ""),
    "nature_of_business": ("No", "", "Up to 1000 characters"),
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
    "individual_mobile_number": (INDIVIDUAL, "", PHONE),
    "individual_email": (INDIVIDUAL, "", "A valid email address"),
    "uae_visa_number": ("No", "", ""),
    "uae_visa_expiry": ("No", "", "Not expired more than 30 days ago when entered"),
    "is_pep": ("No", "Yes / No", "Set automatically when a person on the client is a PEP"),
    "tags": ("No", "Master list: client tags", "Several allowed"),
    "screening_date": ("No", "", FUTURE_NO + "; the screening report is uploaded in the same section"),
    "br_person_met": (AT_SUBMIT, "", "At most 255 characters"),
    "br_meeting_place": (AT_SUBMIT, "", "At most 255 characters"),
    "br_meeting_date": (AT_SUBMIT, "", "Not in the future by the user's own clock (UAE or India); at most 30 days back when entered"),
    "br_meeting_time": (AT_SUBMIT, "", "HH:MM; for a meeting today, not later than now by the user's own clock"),
    "br_meeting_mode": (AT_SUBMIT, "Master list: meeting modes", ""),
    "br_rationale": (AT_SUBMIT, "", ""),
    "engagement_letter_signed": (AT_SUBMIT, "Yes / No", ""),
    "engagement_letter_valid_until": ("When the engagement letter is signed", "", "Any date; past dates allowed"),
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
    "mobile_number": ("No", "", PHONE),
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
    "lost_reason": ("When the prospect is dropped", "", ""),
    "notes": (ALWAYS, "", "Details of the services asked for"),
    "assignor_comments": ("No", "", "Up to 250 words; entered when assigning the prospect to an RM"),
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
    "date_received": ("No", "", FUTURE_NO),
    "date_completed": ("No", "", ""),
    "charge_amount": ("At Submit", "", "More than 0; excluding VAT"),
    "charge_currency": ("With the charge", "AED, USD, EUR, GBP, INR, SGD", ""),
    "amount_paid": ("No", "", ""),
    "amount_paid_currency": ("With the amount paid", "AED, USD, EUR, GBP, INR, SGD", ""),
    "payment_received_date": ("No", "", ""),
    "govt_authority_amount": ("No", "", ""),
    "govt_authority_currency": ("With the amount", "AED, USD, EUR, GBP, INR, SGD", ""),
    "service_provider_involved": ("No", "Yes / No", ""),
    "service_provider_name": ("When a service provider is involved", "", "Up to 150 characters"),
    "service_provider_amount": ("No", "", ""),
    "service_provider_currency": ("With the amount", "AED, USD, EUR, GBP, INR, SGD", ""),
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
    "govt_authority_currency": ("With the amount", "AED, USD, EUR, GBP, INR, SGD", ""),
    "introducer_involved": ("Onboarding invoices, to send", "Yes / No", ""),
    "introducer_amount": ("When an introducer is involved", "", ""),
    "introducer_currency": ("With the amount", "AED, USD, EUR, GBP, INR, SGD", ""),
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
        "party_role": "Role", "residential_address": "Address", "mobile_country_code": "Mobile (country code)",
        "constitution": "Individual / Entity", "full_name": "Full Name", "dob_or_incorp_date": "Date of Birth / Incorporation",
        "id_or_license_expiry": "Passport / Licence Expiry", "passport_number": "Passport Number", "nationality": "Nationality",
        "country_of_incorp_or_birth": "Country of Birth / Incorporation", "country_of_residence": "Country of Residence",
        "mobile_number": "Mobile", "uae_visa_expiry": "UAE Visa Expiry", "is_pep": "PEP", "notes": "Notes",
    },
    "Prospects": {"contact_name": "Contact Name", "contact_email": "Contact Email", "contact_phone": "Contact Phone",
                  "source": "Source", "status": "Status", "owner_id": "Assigned RM", "lost_reason": "Reason for dropping",
                  "assignor_comments": "Assignor's comments", "notes": "Services the prospect is looking for"},
    "Visit & Call Reports": {"client_contact": "Client contact met / spoken to", "location": "Location", "purpose": "Purpose",
                             "outcome": "Outcome", "next_action": "Next action", "status": "Draft / Final"},
    "Service Requests": {"triam_entity": "Triam Entity", "date_received": "Date Received", "date_completed": "Date Completed",
                         "status": "Status", "charge_amount": "Charge to the client (excluding VAT)",
                         "charge_currency": "Charge - currency", "amount_paid": "Amount paid by the client",
                         "amount_paid_currency": "Amount paid - currency", "payment_received_date": "Date amount received by Triam",
                         "govt_authority_amount": "Amount payable to Reg. / Govt Authority",
                         "govt_authority_currency": "Amount payable to Reg. / Govt Authority - currency",
                         "service_provider_amount": "Amount payable to the service provider",
                         "service_provider_currency": "Amount payable to the service provider - currency", "comments": "Comments"},
    "Invoices": {"kind": "Invoice for", "description": "Description", "amount": "Amount", "currency": "Currency", "status": "Status",
                 "raised_date": "Invoice Date", "due_date": "Due Date", "paid_date": "Paid Date",
                 "govt_authority_amount": "Amount payable to the Regn / Govt Authority",
                 "introducer_involved": "Introducer / referrer involved?", "introducer_amount": "Amount payable to the introducer",
                 "co_comment": "Compliance comments", "govt_authority_currency": "Amount payable to the Regn / Govt Authority - currency",
                 "introducer_currency": "Amount payable to the introducer - currency"},
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


# Triam 28-11-2026: fields that hold digits (or letters and digits) but are kept as text, said plainly. Phone numbers
# are stored as text on purpose: a number field would drop a leading 0 and the + of the code, could show 9.71E+11 in
# Excel, and a phone number is never added up. The CRM still accepts digits only (see the Checks column).
DIGITS = "Digits only (kept as text)"
SHOWN_TYPE = {
    "contact_mobile_number": (DIGITS, "8 to 12 digits, by country"), "individual_mobile_number": (DIGITS, "8 to 12 digits, by country"),
    "mobile_number": (DIGITS, "8 to 12 digits, by country"),
    "contact_mobile_country_code": ("Dialling code, e.g. +971", "Up to 6 characters"),
    "individual_mobile_country_code": ("Dialling code, e.g. +971", "Up to 6 characters"),
    "mobile_country_code": ("Dialling code, e.g. +971", "Up to 6 characters"),
    "contact_phone": ("Dialling code and digits (kept as text)", "Up to 50 characters"),
    "mobile": ("Dialling code and digits (kept as text)", "Up to 20 characters"),
    "trn_vat_number": ("Letters and digits (kept as text)", "Up to 30; UAE 15 digits"),
    "corp_tax_registration_number": ("Letters and digits (kept as text)", "Up to 30; UAE 15 digits"),
    "lei_number": ("Letters and digits (kept as text)", "Up to 20 characters"),
    "passport_number": ("Letters and digits (kept as text)", "Up to 20 characters"),
}


def data_type(col) -> tuple[str, str]:
    if col.name in SHOWN_TYPE:
        return SHOWN_TYPE[col.name]
    t = col.type
    if isinstance(t, Boolean):
        return "Yes / No", ""
    if isinstance(t, DateTime):
        return "Date and time", ""
    if isinstance(t, Date):
        return "Date (DD-MM-YYYY)", ""
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


# Client fields are listed under the sections of the onboarding form; a section starts at its first field.
CLIENT_SECTIONS = {
    "anchor_entity": "Basic details", "registration_number": "Incorporation and licence",
    "is_regulated": "Regulatory details", "lei_number": "LEI", "registered_address": "Addresses",
    "trn_vat_number": "Tax details", "has_introducer": "Introducer", "date_of_birth": "Individual clients",
    "is_pep": "PEP, tags and name screening", "br_person_met": "Business rationale",
    "engagement_letter_signed": "Engagement letter", "risk_rating": "CDD / AML (filled by Compliance)",
    "profile_status": "Status and Client ID", "onboarding_invoice_wanted": "Onboarding invoice",
}

# Fields the CRM fills in itself: a plain name and what it holds.
SYSTEM = {
    "id": ("Internal ID", "Running number given by the system"),
    "created_at": ("Created on", "Date and time the record was created"),
    "updated_at": ("Last updated on", "Date and time of the last change"),
    "owner_id": ("Created by", "User who created the record"),
    "account_uid": ("Client reference", "Internal reference of the client record"),
    "prospect_uid": ("Prospect reference", "Internal reference of the prospect"),
    "activity_uid": ("Report reference", "Internal reference of the report"),
    "duplicate_override_reason": ("Duplicate name allowed - reason", "Recorded when a client is saved despite a similar name"),
    "status_updated_at": ("Status changed on", "Date and time of the last status change"),
    "status_updated_by_id": ("Status changed by", "User who made the last status change"),
    "approved_at": ("Approved on", "Date and time of the Final approval"),
    "aml_classification": ("AML classification", "Older field, not shown on the screens"),
    "prospect_id": ("From prospect", "The prospect this client was converted from"),
    "account_id": ("Client", "The client this record belongs to"),
    "removed_at": ("Removed on", "Date and time the person was removed"),
    "removed_by_id": ("Removed by", "User who removed the person"),
    "removed_reason": ("Reason for removal", "Entered when removing the person"),
    "proposal_sent_date": ("Proposal sent on", "Shown on the prospect"),
    "proposal_amount": ("Proposal amount", "Older field, not shown on the screens"),
    "expected_close_date": ("Expected close date", "Older field, not shown on the screens"),
    "next_follow_up_date": ("Next follow-up date", "Older field, not shown on the screens"),
    "converted_account_id": ("Converted to client", "The client created from this prospect"),
    "assigned_by_id": ("Assigned by", "User who assigned the prospect to the RM"),
    "assigned_at": ("Assigned on", "Date and time of the assignment"),
    "company_name": ("Client name", "Copied from the client when the report is saved"),
    "cancel_reason": ("Reason for cancelling", "Entered when cancelling"),
    "finalised_at": ("Finalised on", "Date and time the report was made final"),
    "finalised_by_id": ("Finalised by", "User who made the report final"),
    "invoice_id": ("Invoice", "The invoice raised for this request"),
    "submitted_at": ("Submitted on", "Date and time the request was submitted"),
    "submitted_by_id": ("Submitted by", "User who submitted the request"),
    "requested_by_id": ("Requested by", "User who asked for the invoice"),
    "requested_at": ("Requested on", "Date and time the invoice was asked for"),
    "raised_by_id": ("Raised by", "Accounts user who raised the invoice"),
    "co_decided_by_id": ("Compliance decision by", "Compliance user who approved or returned it"),
    "co_decided_at": ("Compliance decision on", "Date and time of the Compliance decision"),
    "co_decision": ("Compliance decision", "Approved / Returned"),
    "hashed_password": ("Password", "Stored encrypted; never shown"),
    "is_super_admin": ("Super administrator", "Set by the system administrator only"),
    "failed_login_count": ("Failed sign-in attempts", "5 in a row lock the user for 15 minutes"),
    "locked_until": ("Locked until", "Set after 5 failed sign-in attempts"),
    "password_changed_at": ("Password changed on", "Date and time of the last password change"),
    "signed_out_at": ("Signed out on", "Date and time of the last sign-out"),
    "last_login_at": ("Last sign-in", "Date and time of the last sign-in"),
    "previous_login_at": ("Previous sign-in", "Shown to the user at sign-in"),
    "person_id": ("Linked person", "Links the logins of one person"),
}

COUNTRY_NAMES = {
    "+971": "United Arab Emirates", "+91": "India", "+1": "USA / Canada", "+44": "United Kingdom", "+92": "Pakistan",
    "+63": "Philippines", "+20": "Egypt", "+966": "Saudi Arabia", "+974": "Qatar", "+973": "Bahrain", "+965": "Kuwait",
    "+968": "Oman", "+65": "Singapore", "+852": "Hong Kong",
}

SHEET_TITLES = {
    "Clients": "Client details (New Client Onboarding and Client Data Maintenance)",
    "People": "Shareholders, directors, signatories and other persons on a client",
    "Prospects": "Prospects",
    "Visit & Call Reports": "Visit reports and call reports",
    "Service Requests": "Service requests",
    "Invoices": "Invoices (onboarding and service requests)",
    "Users": "Users (Admin)",
}


def humanize(name: str) -> str:
    return name.replace("_ids", "").replace("_id", "").replace("_", " ").capitalize()


FONT = "Calibri"
_thin = Side(style="thin", color="BFC5CD")
BORDER = Border(top=_thin, bottom=_thin, left=_thin, right=_thin)
HEAD_FILL = PatternFill("solid", fgColor=BRAND)
SECTION_FILL = PatternFill("solid", fgColor="DCE6F0")
GREY_FILL = PatternFill("solid", fgColor="F2F2F2")
WRAP = Alignment(vertical="top", wrap_text=True)
CENTER = Alignment(vertical="top", horizontal="center")


def _cell(ws, row, col, value, bold=False, size=10, color="000000", fill=None, align=WRAP, border=True, italic=False):
    c = ws.cell(row=row, column=col, value=value)
    c.font = Font(name=FONT, bold=bold, size=size, color=color, italic=italic)
    c.alignment = align
    if fill:
        c.fill = fill
    if border:
        c.border = BORDER
    return c


def _band(ws, row, text, ncols):
    for j in range(1, ncols + 1):
        _cell(ws, row, j, text if j == 1 else None, bold=True, fill=SECTION_FILL)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)


def _cover(ws, counts):
    ws.title = "Cover"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 32
    ws.column_dimensions["C"].width = 80
    _cell(ws, 2, 2, "Triam CRM", bold=True, size=18, color=BRAND, border=False)
    _cell(ws, 3, 2, "Data Dictionary", bold=True, size=14, border=False)
    r = 5
    for k, v in (("Client", "Triam"), ("Document", "Data dictionary of the Triam CRM (UAT)"), ("Version", "1.0"),
                 ("Date", f"{date.today():%d-%m-%Y}"), ("Prepared by", "Manu")):
        _cell(ws, r, 2, k, bold=True, fill=GREY_FILL)
        _cell(ws, r, 3, v)
        r += 1

    r += 1
    _cell(ws, r, 2, "Purpose", bold=True, size=12, color=BRAND, border=False)
    r += 1
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
    _cell(ws, r, 2, "This document lists the fields on each screen of the CRM: the field name as shown on screen, the "
                    "name it is stored under, its data type and length, whether it is mandatory, the values allowed and "
                    "the validations applied. Please go through it and share your comments or suggestions, if any.",
          border=False)
    ws.row_dimensions[r].height = 45

    r += 2
    _cell(ws, r, 2, "Contents", bold=True, size=12, color=BRAND, border=False)
    r += 1
    _cell(ws, r, 2, "Sheet", bold=True, color="FFFFFF", fill=HEAD_FILL)
    _cell(ws, r, 3, "What it covers", bold=True, color="FFFFFF", fill=HEAD_FILL)
    for title, *_ in SHEETS:
        r += 1
        entered, system = counts[title]
        _cell(ws, r, 2, title)
        _cell(ws, r, 3, f"{SHEET_TITLES[title]} - {entered} fields, plus {system} maintained by the system")
    r += 1
    _cell(ws, r, 2, "Phone Number Lengths")
    _cell(ws, r, 3, "Number of digits allowed in a phone number, by country code")

    r += 2
    _cell(ws, r, 2, "How to read the sheets", bold=True, size=12, color=BRAND, border=False)
    notes = (
        ("Mandatory: Always", "The record cannot be saved without it."),
        ("Mandatory: At Submit", "The client can be saved as a draft without it, but cannot be submitted for approval until it is filled."),
        ("Mandatory: At Compliance approval", "Filled by Compliance (CO / MLRO) before giving the Compliance approval."),
        ("Master list", "Values maintained by the Administrator under Admin > Master Data."),
        ("Maintained by the system", "Fields the CRM fills in on its own (references, and the dates and users of changes). "
                                     "Listed at the end of each sheet."),
        ("Phone, tax and passport numbers", "Kept as text and not as numbers, so that a leading 0 and the country code are "
                                            "not lost. The screens still accept only digits (or letters and digits), as given "
                                            "in the Validations column."),
        ("Dates", "Shown and entered as DD-MM-YYYY."),
    )
    r += 1
    for k, v in notes:
        _cell(ws, r, 2, k, bold=True, fill=GREY_FILL)
        _cell(ws, r, 3, v)
        r += 1
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def _phone_sheet(wb):
    lengths = json.loads((ROOT / "backend" / "app" / "data" / "phone_lengths.json").read_text(encoding="utf-8"))
    ws = wb.create_sheet("Phone Number Lengths")
    ws.sheet_view.showGridLines = False
    for col, w in zip("ABCD", (8, 12, 28, 30)):
        ws.column_dimensions[col].width = w
    _cell(ws, 1, 1, "Phone number lengths by country", bold=True, size=13, color=BRAND, border=False, align=Alignment())
    _cell(ws, 2, 1, "Number of digits after the country code. Applies to every mobile / contact number field.",
          italic=True, color="595959", border=False, align=Alignment())
    for j, h in enumerate(("S.No.", "Code", "Country", "Digits allowed"), start=1):
        _cell(ws, 4, j, h, bold=True, color="FFFFFF", fill=HEAD_FILL)
    rows = [(code, COUNTRY_NAMES.get(code, ""), "9 (mobile) or 8 (landline)" if code == "+971" else
             (f"{lo}" if lo == hi else f"{lo} to {hi}"))
            for code, (lo, hi) in ((k, v) for k, v in lengths.items() if k.startswith("+"))]
    lo, hi = lengths["default"]
    rows.append(("Others", "Any other country", f"{lo} to {hi}"))
    for n, (code, country, digits) in enumerate(rows, start=1):
        for j, v in enumerate((n, code, country, digits), start=1):
            _cell(ws, 4 + n, j, v, align=CENTER if j < 3 else WRAP)


def build(path: Path) -> None:
    wb = Workbook()
    cover = wb.active
    head = ("S.No.", "Field name (on screen)", "Database field", "Data type", "Max length", "Mandatory",
            "Allowed values / source", "Validations / remarks")
    widths = (7, 34, 28, 22, 18, 30, 40, 58)
    counts = {}
    for title, model, rules, forms in SHEETS:
        ws = wb.create_sheet(title)
        labels = labels_from(*forms)
        for j, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(j)].width = w
        _cell(ws, 1, 1, SHEET_TITLES[title], bold=True, size=13, color=BRAND, border=False, align=Alignment(vertical="center"))
        ws.row_dimensions[1].height = 22
        for j, h in enumerate(head, start=1):
            _cell(ws, 3, j, h, bold=True, color="FFFFFF", fill=HEAD_FILL, align=Alignment(vertical="center", wrap_text=True))
        ws.row_dimensions[3].height = 30

        cols = list(model.__table__.columns)
        order = list(rules)
        entered = sorted([c for c in cols if c.name in rules], key=lambda c: order.index(c.name))
        system = [c for c in cols if c.name not in rules]
        counts[title] = (len(entered), len(system))

        r, n = 4, 0
        _band(ws, r, "A. Fields entered by the users", len(head))
        for col in entered:
            if title == "Clients" and col.name in CLIENT_SECTIONS:
                r += 1
                for j in range(1, len(head) + 1):
                    _cell(ws, r, j, None)
                _cell(ws, r, 2, CLIENT_SECTIONS[col.name], bold=True, italic=True, color=BRAND)
            n += 1
            r += 1
            dtype, length = data_type(col)
            mand, allowed, checks = rules[col.name]
            label = LABELS.get(title, {}).get(col.name) or labels.get(col.name) or humanize(col.name)
            for j, v in enumerate((n, label, col.name, dtype, length, mand, allowed, checks), start=1):
                _cell(ws, r, j, v or None, align=CENTER if j == 1 else WRAP)
        r += 1
        _band(ws, r, "B. Fields maintained by the system", len(head))
        for col in system:
            n += 1
            r += 1
            dtype, length = data_type(col)
            label, remark = SYSTEM.get(col.name, (humanize(col.name), ""))
            for j, v in enumerate((n, label, col.name, dtype, length, "System", "", remark), start=1):
                _cell(ws, r, j, v or None, color="595959", align=CENTER if j == 1 else WRAP)
        ws.freeze_panes = "C4"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = "3:3"
        ws.oddFooter.left.text = "Triam CRM - Data Dictionary"
        ws.oddFooter.right.text = "Page &P of &N"
    _cover(cover, counts)
    _phone_sheet(wb)
    wb.properties.creator = "Manu"
    wb.properties.lastModifiedBy = "Manu"
    wb.properties.title = "Triam CRM - Data Dictionary"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    print("written", path)


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "Triam_CRM_Data_Dictionary.xlsx"))
