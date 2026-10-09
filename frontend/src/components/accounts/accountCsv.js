import { csvDate } from "../../utils/constants";
// CSV import/export for the Clients page. Pure functions (no React, no API) so they can be unit-tested.

const IMPORT_ADDRESS_COL_KEYS = { "line 1": "line1", "line 2": "line2", "landmark": "landmark", "city": "city", "zip": "zip", "p.o. box": "po_box", "country": "country" };
const IMPORT_BOOLEAN_FIELDS = new Set(["is_regulated", "corp_tax_registered", "has_introducer", "engagement_letter_signed"]);
const IMPORT_TRUTHY = new Set(["true", "yes", "1"]);

export const IMPORT_HEADER_MAP = {
  "client type": "account_type",
  "unique search name": "search_name", // BRD §3. "Client ID" is export-only: IDs are always issued by the system.
  "company name": "company_name",
  "industry": "industry",
  "country": "country",
  "website": "website",
  "key contacts": "key_contacts",
  "single point of contact": "single_point_of_contact",
  "anchor entity": "anchor_entity",
  "non-anchor entities": "__non_anchor_entities",
  "strategic priority": "strategic_priority",
  "existing relationship": "existing_relationship",
  "tags": "tags",
  "incorporation certificate no.": "registration_number",
  "registration number": "registration_number", // legacy header, kept for older exported files
  "incorporation date": "incorporation_date",
  "license number": "license_number",
  "risk rating": "risk_rating",
  "kyc status": "kyc_status",
  "spoc": "__spoc_name", // legacy header, kept for older exported files
  "anchor rm (spoc)": "__spoc_name",
  "non-anchor rms": "__non_anchor_rm_names",
  "licensing authority": "licensing_authority",
  "license activities": "license_activities",
  "license start date": "license_start_date",
  "license expiry date": "license_expiry_date",
  "is regulated": "is_regulated",
  "regulator": "regulator_name",
  "other regulator": "regulator_other",
  "license category": "license_category",
  "trn/vat number": "trn_vat_number",
  "corp tax registered": "corp_tax_registered",
  "corp tax registration no.": "corp_tax_registration_number",
  "financial year end": "financial_year_end",
  "has introducer": "has_introducer",
  "introducer name": "introducer_name",
  "services obtained": "__services_obtained",
  "nature of services sought": "__nature_of_services_sought",
  "profile status": "profile_status",
  "engagement letter signed": "engagement_letter_signed",
  "engagement letter valid until": "engagement_letter_valid_until",
  "aml classification": "aml_classification",
  "edd reason": "edd_reason",
  "cdd completion date": "cdd_completion_date",
  "date of birth": "date_of_birth",
  "country of birth": "country_of_birth",
  "nationality": "nationality",
  "passport number": "passport_number",
  "passport expiry": "passport_expiry_date",
  "occupation": "occupation",
  "source of funds": "source_of_funds",
  "source of wealth": "source_of_wealth",
  "country of residence": "country_of_residence",
  "individual mobile": "individual_mobile", // legacy header, kept for older exported files
  "individual mobile country code": "individual_mobile_country_code",
  "individual mobile number": "individual_mobile_number",
  "individual email": "individual_email",
  "uae visa number": "uae_visa_number",
  "uae visa expiry": "uae_visa_expiry",
};
for (const [prefix, target] of [["registered address", "registered_address"], ["operating address", "operating_address"], ["residential address", "residential_address"]]) {
  for (const [col, subKey] of Object.entries(IMPORT_ADDRESS_COL_KEYS)) {
    IMPORT_HEADER_MAP[`${prefix} ${col}`] = `${target}.${subKey}`;
  }
}

const splitList = (value) => value.split(";").map((s) => s.trim()).filter(Boolean);

// Minimal RFC-4180-ish CSV reader: handles quoted fields, escaped "" quotes, commas/newlines inside quotes.
// Returns the raw table (header row first) as arrays of strings; blank lines are dropped.
export function parseCSVTable(text) {
  const rows = [];
  let row = [], field = "", inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') { inQuotes = false; }
      else { field += c; }
    } else if (c === '"') { inQuotes = true; }
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.some((v) => v !== "")) rows.push(row);
      row = [];
    } else { field += c; }
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows;
}

// Client CSV: one object per data row, keyed by account field name (see IMPORT_HEADER_MAP).
// Dates written by the export (DD/MM/YYYY) or typed in Excel (DD-MM-YYYY, DD MM YYYY) go back to ISO.
const dmyToIso = (v) => {
  const m = v.match(/^(\d{2})[/\- .](\d{2})[/\- .](\d{4})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : v;
};

export function parseCSV(text) {
  const rows = parseCSVTable(text);
  if (rows.length === 0) return [];
  const headers = rows[0].map((h) => h.trim().toLowerCase());
  return rows.slice(1).map((r) => {
    const obj = {};
    headers.forEach((h, i) => {
      const key = IMPORT_HEADER_MAP[h];
      const value = (r[i] || "").trim();
      if (!key || !value) return;
      if (key.includes(".")) {
        const [parent, child] = key.split(".");
        obj[parent] = { ...(obj[parent] || {}), [child]: value };
      } else if (key === "__services_obtained") {
        obj.services_obtained = splitList(value);
      } else if (key === "__nature_of_services_sought") {
        obj.nature_of_services_sought = splitList(value);
      } else if (key === "__non_anchor_entities") {
        obj.non_anchor_entities = splitList(value);
      } else if (key === "__spoc_name" || key === "__non_anchor_rm_names") {
        obj[key] = value;
      } else if (IMPORT_BOOLEAN_FIELDS.has(key)) {
        obj[key] = IMPORT_TRUTHY.has(value.toLowerCase());
      } else {
        obj[key] = dmyToIso(value);
      }
    });
    return obj;
  });
}

// Parses an import file into account payloads ready for accountsApi.import: drops rows without a
// company name and resolves RM names (case-insensitive) to user ids.
export function parseImportRows(text, users) {
  const userByName = (name) => users.find((u) => u.name.toLowerCase() === name.toLowerCase());
  return parseCSV(text).filter((r) => r.company_name).map((row) => {
    const { __spoc_name, __non_anchor_rm_names, ...rest } = row;
    if (__spoc_name) {
      const match = userByName(__spoc_name);
      if (match) rest.spoc_id = match.id;
    }
    if (__non_anchor_rm_names) {
      rest.non_anchor_rm_ids = __non_anchor_rm_names.split(";").map((s) => userByName(s.trim())?.id).filter(Boolean);
    }
    return rest;
  });
}

const ADDRESS_COLS = ["Line 1", "Line 2", "Landmark", "City", "ZIP", "P.O. Box", "Country"];
const addrRow = (v) => { const a = v || {}; return [a.line1, a.line2, a.landmark, a.city, a.zip, a.po_box, a.country]; };

export const EXPORT_HEADERS = [
  "Account UID", "Client ID", "Unique Search Name", "Client Type", "Company Name", "Industry", "Country", "Website", "Key Contacts", "Single Point of Contact",
  "Anchor Entity", "Non-anchor Entities",
  "Strategic Priority", "Existing Relationship", "Tags", "Incorporation Certificate No.", "Incorporation Date", "License Number",
  "Risk Rating", "KYC Status", "Anchor RM (SPOC)", "Non-anchor RMs",
  "Licensing Authority", "License Activities", "License Start Date", "License Expiry Date",
  "Is Regulated", "Regulator", "Other Regulator", "License Category",
  ...ADDRESS_COLS.map((c) => `Registered Address ${c}`),
  ...ADDRESS_COLS.map((c) => `Operating Address ${c}`),
  "TRN/VAT Number", "Corp Tax Registered", "Corp Tax Registration No.", "Financial Year End",
  "Has Introducer", "Introducer Name", "Services Obtained",
  "Profile Status", "Engagement Letter Signed", "Engagement Letter Valid Until",
  "AML Classification", "EDD Reason", "CDD Completion Date", "Next AML Review Date", "Is PEP",
  "Date of Birth", "Country of Birth", "Nationality", "Passport Number", "Passport Expiry", "Occupation",
  "Source of Funds", "Source of Wealth", "Country of Residence",
  ...ADDRESS_COLS.map((c) => `Residential Address ${c}`),
  "Individual Mobile Country Code", "Individual Mobile Number", "Individual Email", "UAE Visa Number", "UAE Visa Expiry", "Nature of Services Sought",
  "Total Cases", "Total Invoiced Amount", "Created At", "Updated At",
];

// Builds the export CSV text. Headers are chosen so the file round-trips through parseCSV.
export function buildAccountsCsv(accounts, users) {
  const userName = (id) => users.find((u) => u.id === id)?.name;
  const rows = accounts.map((a) => [
    a.account_uid, a.client_id, a.search_name, a.account_type, a.company_name, a.industry, a.country, a.website, a.key_contacts, a.single_point_of_contact,
    a.anchor_entity, (a.non_anchor_entities || []).join("; "),
    a.strategic_priority, a.existing_relationship, a.tags, a.registration_number, a.incorporation_date, a.license_number,
    a.risk_rating, a.kyc_status, userName(a.spoc_id) || "",
    (a.non_anchor_rm_ids || []).map(userName).filter(Boolean).join("; "),
    a.licensing_authority, a.license_activities, a.license_start_date, a.license_expiry_date,
    a.is_regulated, a.regulator_name, a.regulator_other, a.license_category,
    ...addrRow(a.registered_address),
    ...addrRow(a.operating_address),
    a.trn_vat_number, a.corp_tax_registered, a.corp_tax_registration_number, a.financial_year_end,
    a.has_introducer, a.introducer_name, (a.services_obtained || []).join("; "),
    a.profile_status, a.engagement_letter_signed, a.engagement_letter_valid_until,
    a.aml_classification, a.edd_reason, a.cdd_completion_date, a.next_aml_review_date, a.is_pep,
    a.date_of_birth, a.country_of_birth, a.nationality, a.passport_number, a.passport_expiry_date, a.occupation,
    a.source_of_funds, a.source_of_wealth, a.country_of_residence,
    ...addrRow(a.residential_address),
    a.individual_mobile_country_code, a.individual_mobile_number, a.individual_email, a.uae_visa_number, a.uae_visa_expiry,
    (a.nature_of_services_sought || []).join("; "),
    a.total_cases, a.total_invoiced_amount, a.created_at, a.updated_at,
  ]);
  return [EXPORT_HEADERS, ...rows].map((r) => r.map((v) => `"${(csvDate(v) ?? "").toString().replace(/"/g, '""')}"`).join(",")).join("\n");
}
