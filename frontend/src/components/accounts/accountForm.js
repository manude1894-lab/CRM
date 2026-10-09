// Client (account) form state helpers: blank form, account → form mapping, and form → API payload.
// Pure functions so they can be unit-tested without rendering the form.

export const PRIORITY_OPTIONS = ["Low", "Medium", "High"];
export const RISK_OPTIONS = ["Low", "Medium", "High"];
export const KYC_STATUS_OPTIONS = ["Not Started", "Submitted", "Under Review", "Approved", "Rejected"];

export const BLANK_ADDRESS = { line1: "", line2: "", landmark: "", zip: "", po_box: "", city: "", country: "" };

export const BLANK_ACCOUNT_FORM = {
  account_type: "Corporate",
  company_name: "", search_name: "", industry: "", country: "", strategic_priority: "Medium", existing_relationship: "No",
  key_contacts: "", single_point_of_contact: "", website: "", spoc_id: "", non_anchor_rm_ids: [], anchor_entity: "", non_anchor_entities: [], registration_number: "", incorporation_date: "", license_number: "", risk_rating: "", kyc_status: "Not Started",
  licensing_authority: "", licensing_authority_other: "", license_start_date: "", license_expiry_date: "", regulatory_license_expiry_date: "", is_regulated: null, regulator_name: "", regulator_other: "",
  license_category: "", license_activities: "",
  registered_address: { ...BLANK_ADDRESS }, operating_address: { ...BLANK_ADDRESS },
  trn_vat_number: "", corp_tax_registered: null, corp_tax_registration_number: "",
  financial_year_end: "", has_introducer: null, introducer_name: "",
  services_obtained: [], tags: [],
  profile_status: "New",
  engagement_letter_signed: false, engagement_letter_valid_until: "",
  aml_classification: "", edd_reason: "", cdd_completion_date: "", kyc_verified_by: "",
  is_pep: false,
  date_of_birth: "", country_of_birth: "", nationality: "", passport_number: "", passport_expiry_date: "", occupation: "",
  source_of_funds: "", source_of_wealth: "", country_of_residence: "",
  residential_address: { ...BLANK_ADDRESS },
  individual_mobile: "", individual_mobile_country_code: "+971", individual_mobile_number: "",
  individual_email: "", uae_visa_number: "", uae_visa_expiry: "", nature_of_services_sought: [],
};

// Field groups saved by each section's own Save button (client CRM-change-request item 19).
export const SECTION_FIELDS = {
  core: [
    "account_type", "company_name", "search_name", "industry", "country", "website", "key_contacts",
    "single_point_of_contact", "strategic_priority", "existing_relationship", "spoc_id", "non_anchor_rm_ids",
    "anchor_entity", "non_anchor_entities", "registration_number", "license_number", "incorporation_date",
    "risk_rating", "kyc_status", "tags",
  ],
  licensing: ["licensing_authority", "licensing_authority_other", "license_start_date", "license_expiry_date", "license_activities", "is_regulated", "regulator_name", "regulator_other", "license_category", "regulatory_license_expiry_date"],
  registeredAddress: ["registered_address"],
  operatingAddress: ["operating_address"],
  tax: ["trn_vat_number", "financial_year_end", "corp_tax_registered", "corp_tax_registration_number"],
  individual: [
    "date_of_birth", "country_of_birth", "nationality", "passport_number", "passport_expiry_date", "occupation",
    "source_of_funds", "source_of_wealth", "country_of_residence", "residential_address",
    "individual_mobile_country_code", "individual_mobile_number", "individual_email",
    "uae_visa_number", "uae_visa_expiry", "nature_of_services_sought", "is_pep",
  ],
  introducer: ["has_introducer", "introducer_name"],
  services: ["services_obtained"],
  // Status itself only changes through the workflow (P2) — this section saves engagement only.
  profileStatus: ["engagement_letter_valid_until", "engagement_letter_signed"],
  aml: ["aml_classification", "cdd_completion_date", "edd_reason", "kyc_verified_by"],
};

// Maps an account from the API into editable form state (nulls → "", tags string → array).
export function accountToForm(a) {
  return {
    account_type: a.account_type || "Corporate",
    company_name: a.company_name, search_name: a.search_name || "", industry: a.industry || "", country: a.country || "", strategic_priority: a.strategic_priority,
    existing_relationship: a.existing_relationship, key_contacts: a.key_contacts || "", single_point_of_contact: a.single_point_of_contact || "", website: a.website || "", spoc_id: a.spoc_id || "", non_anchor_rm_ids: a.non_anchor_rm_ids || [],
    anchor_entity: a.anchor_entity || "", non_anchor_entities: a.non_anchor_entities || [],
    registration_number: a.registration_number || "", incorporation_date: a.incorporation_date || "", license_number: a.license_number || "", risk_rating: a.risk_rating || "", kyc_status: a.kyc_status || "Not Started",
    licensing_authority: a.licensing_authority || "", licensing_authority_other: a.licensing_authority_other || "", license_start_date: a.license_start_date || "", license_expiry_date: a.license_expiry_date || "",
    is_regulated: a.is_regulated ?? null, regulatory_license_expiry_date: a.regulatory_license_expiry_date || "", regulator_name: a.regulator_name || "", regulator_other: a.regulator_other || "",
    license_category: a.license_category || "", license_activities: a.license_activities || "",
    registered_address: { ...BLANK_ADDRESS, ...(a.registered_address || {}) }, operating_address: { ...BLANK_ADDRESS, ...(a.operating_address || {}) },
    trn_vat_number: a.trn_vat_number || "", corp_tax_registered: a.corp_tax_registered ?? null, corp_tax_registration_number: a.corp_tax_registration_number || "",
    financial_year_end: a.financial_year_end || "", has_introducer: a.has_introducer ?? null, introducer_name: a.introducer_name || "",
    services_obtained: a.services_obtained || [], tags: a.tags ? a.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
    profile_status: a.profile_status || "New",
    engagement_letter_signed: !!a.engagement_letter_signed, engagement_letter_valid_until: a.engagement_letter_valid_until || "",
    aml_classification: a.aml_classification || "", edd_reason: a.edd_reason || "", cdd_completion_date: a.cdd_completion_date || "",
    kyc_verified_by: a.kyc_verified_by || "",
    next_aml_review_date: a.next_aml_review_date || null,
    is_pep: !!a.is_pep,
    date_of_birth: a.date_of_birth || "", country_of_birth: a.country_of_birth || "", nationality: a.nationality || "", passport_number: a.passport_number || "",
    passport_expiry_date: a.passport_expiry_date || "", occupation: a.occupation || "",
    source_of_funds: a.source_of_funds || "", source_of_wealth: a.source_of_wealth || "", country_of_residence: a.country_of_residence || "",
    residential_address: { ...BLANK_ADDRESS, ...(a.residential_address || {}) },
    individual_mobile: a.individual_mobile || "", individual_mobile_country_code: a.individual_mobile_country_code || "",
    individual_mobile_number: a.individual_mobile_number || "", individual_email: a.individual_email || "",
    uae_visa_number: a.uae_visa_number || "", uae_visa_expiry: a.uae_visa_expiry || "",
    nature_of_services_sought: a.nature_of_services_sought || [],
    _id: a.id,
    // Read-only, shown in the profile header (BRD §11 / §19).
    _client_id: a.client_id || null,
    _status_updated_at: a.status_updated_at || null,
  };
}

// Empty-string optional date fields must become null (FastAPI can't parse "" as a date).
export const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

const toSpocId = (v) => (v ? +v : null);

// Full-form payload for create/update. `_id` and the server-computed next_aml_review_date are stripped.
export function buildAccountPayload(form) {
  // profile_status is never sent: it changes only through Submit / Approve / status actions (BRD §11).
  const { next_aml_review_date, tags, _id, _client_id, _status_updated_at, profile_status, ...rest } = form;
  const payload = cleanPayload({ ...rest, tags: (tags || []).join(", ") || null });
  return { ...payload, spoc_id: toSpocId(payload.spoc_id) };
}

// Partial payload containing only the given fields, for a single section's Save.
export function buildSectionPatch(form, fieldKeys) {
  const picked = {};
  for (const k of fieldKeys) picked[k] = form[k];
  if ("tags" in picked) picked.tags = (picked.tags || []).join(", ") || null;
  const clean = cleanPayload(picked);
  if ("spoc_id" in clean) clean.spoc_id = toSpocId(clean.spoc_id);
  return clean;
}

// Returns an error message, or null when the core fields are valid for creating a client.
export function validateCoreFields(form) {
  if (!form.company_name?.trim()) return "Company name is required";
  // BRD §19 — the Client ID is built from the Anchor Triam Entity.
  if (!form.anchor_entity) return "Anchor Triam Entity is required (it determines the Client ID)";
  if (form.account_type !== "Individual" && !form.industry?.trim()) return "Industry is required";
  return null;
}
