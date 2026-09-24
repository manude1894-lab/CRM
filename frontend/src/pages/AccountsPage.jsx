import React, { useEffect, useRef, useState } from "react";
import { accountsApi, casesApi, usersApi, amlApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, MultiSelect, CountrySelect, Spinner, ErrorBanner, Textarea } from "../components/ui";
import AccountPartyModal from "../components/AccountPartyModal";
import TrackRecordModal from "../components/TrackRecordModal";
import DocumentsPanel from "../components/DocumentsPanel";
import DuplicateWarning from "../components/DuplicateWarning";
import {
  fmt, fmtDate, REGULATOR_OPTIONS, TAG_OPTIONS, SERVICES_OBTAINED_OPTIONS,
  PROFILE_STATUS_OPTIONS, AML_CLASSIFICATION_OPTIONS, COUNTRY_CALLING_CODES, TRIAM_ENTITY_OPTIONS,
} from "../utils/constants";
import { useAuthStore } from "../store/auth";

const PRIORITY_OPTIONS = ["Low", "Medium", "High"];
const RISK_OPTIONS = ["Low", "Medium", "High"];
const KYC_STATUS_OPTIONS = ["Not Started", "Submitted", "Under Review", "Approved", "Rejected"];

const BLANK_ADDRESS = { line1: "", line2: "", landmark: "", zip: "", po_box: "", city: "", country: "" };

const Section = ({ title, children, hasData, onSave, status, error }) => {
  const [open, setOpen] = useState(!!hasData);
  return (
    <div className="mb-2 border border-gray-100 rounded-lg overflow-hidden">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
          {title}
          {hasData && <span className="w-1.5 h-1.5 rounded-full bg-brand-500 flex-shrink-0" />}
        </span>
        <Icon name="chevronRight" size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="px-3 py-3">
          {children}
          {onSave && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
              <button type="button" onClick={onSave} disabled={status === "saving"}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-50">
                {status === "saving" ? "Saving…" : `Save ${title}`}
              </button>
              {status === "saved" && <span className="text-xs text-emerald-600">Saved</span>}
              {status === "error" && <span className="text-xs text-red-600">{error || "Save failed"}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const AddressFields = ({ value, onChange }) => {
  const v = value || BLANK_ADDRESS;
  const set = (k) => (e) => onChange({ ...v, [k]: e.target.value });
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Address Line 1"><Input value={v.line1 || ""} onChange={set("line1")} /></Field>
      <Field label="Address Line 2"><Input value={v.line2 || ""} onChange={set("line2")} /></Field>
      <Field label="Landmark"><Input value={v.landmark || ""} onChange={set("landmark")} /></Field>
      <Field label="City"><Input value={v.city || ""} onChange={set("city")} /></Field>
      <Field label="ZIP Code"><Input value={v.zip || ""} onChange={set("zip")} /></Field>
      <Field label="P.O. Box No."><Input value={v.po_box || ""} onChange={set("po_box")} /></Field>
      <Field label="Country"><Input value={v.country || ""} onChange={set("country")} /></Field>
    </div>
  );
};

const IMPORT_ADDRESS_COL_KEYS = { "line 1": "line1", "line 2": "line2", "landmark": "landmark", "city": "city", "zip": "zip", "p.o. box": "po_box", "country": "country" };
const IMPORT_BOOLEAN_FIELDS = new Set(["is_regulated", "corp_tax_registered", "has_introducer", "engagement_letter_signed"]);
const IMPORT_TRUTHY = new Set(["true", "yes", "1"]);

const IMPORT_HEADER_MAP = {
  "client type": "account_type",
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
  "spoc": "__spoc_name",
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

// Minimal RFC-4180-ish CSV parser: handles quoted fields, escaped "" quotes, commas/newlines inside quotes.
function parseCSV(text) {
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
        obj.services_obtained = value.split(";").map((s) => s.trim()).filter(Boolean);
      } else if (key === "__nature_of_services_sought") {
        obj.nature_of_services_sought = value.split(";").map((s) => s.trim()).filter(Boolean);
      } else if (key === "__non_anchor_entities") {
        obj.non_anchor_entities = value.split(";").map((s) => s.trim()).filter(Boolean);
      } else if (key === "__spoc_name") {
        obj.__spoc_name = value;
      } else if (IMPORT_BOOLEAN_FIELDS.has(key)) {
        obj[key] = IMPORT_TRUTHY.has(value.toLowerCase());
      } else {
        obj[key] = value;
      }
    });
    return obj;
  });
}

export default function AccountsPage({ initialAccountId } = {}) {
  const appliedInitialRef = useRef(false);
  const [accounts, setAccounts] = useState([]);
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [modal, setModal] = useState(null); // "new" | "edit" | null
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [importPreview, setImportPreview] = useState(null); // { rows, results, created, skipped }
  const [importing, setImporting] = useState(false);
  const [partiesAccount, setPartiesAccount] = useState(null); // Account being edited in AccountPartyModal
  const [trackRecordAccount, setTrackRecordAccount] = useState(null); // Account being viewed in TrackRecordModal
  const [attachmentsAccount, setAttachmentsAccount] = useState(null); // Account whose Attachments modal is open
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkValues, setBulkValues] = useState({ spoc_id: "", risk_rating: "", kyc_status: "" });
  const [bulkApplying, setBulkApplying] = useState(false);
  const fileInputRef = useRef(null);
  const isAdmin = useAuthStore((s) => s.isAdmin());

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [accRes, caseRes, usersRes, countriesRes] = await Promise.all([
        accountsApi.list({ limit: 200 }), casesApi.list({ limit: 500 }), usersApi.list(), amlApi.countryRisk().catch(() => []),
      ]);
      setAccounts(accRes.items || []);
      setCases(caseRes.items || []);
      setUsers(usersRes || []);
      setCountries(countriesRes || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load clients");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!appliedInitialRef.current && initialAccountId && accounts.some((a) => a.id === initialAccountId)) {
      setSelectedId(initialAccountId);
      appliedInitialRef.current = true;
    }
  }, [initialAccountId, accounts]);

  const BLANK = {
    account_type: "Corporate",
    company_name: "", industry: "", country: "", strategic_priority: "Medium", existing_relationship: "No",
    key_contacts: "", single_point_of_contact: "", website: "", spoc_id: "", anchor_entity: "", non_anchor_entities: [], registration_number: "", incorporation_date: "", license_number: "", risk_rating: "", kyc_status: "Not Started",
    licensing_authority: "", license_start_date: "", license_expiry_date: "", is_regulated: false, regulator_name: "", regulator_other: "",
    license_category: "", license_activities: "",
    registered_address: { ...BLANK_ADDRESS }, operating_address: { ...BLANK_ADDRESS },
    trn_vat_number: "", corp_tax_registered: false, corp_tax_registration_number: "",
    financial_year_end: "", has_introducer: false, introducer_name: "",
    services_obtained: [], tags: [],
    profile_status: "New",
    engagement_letter_signed: false, engagement_letter_valid_until: "",
    aml_classification: "", edd_reason: "", cdd_completion_date: "",
    is_pep: false,
    date_of_birth: "", country_of_birth: "", nationality: "", passport_number: "", passport_expiry_date: "", occupation: "",
    source_of_funds: "", source_of_wealth: "", country_of_residence: "",
    residential_address: { ...BLANK_ADDRESS },
    individual_mobile: "", individual_mobile_country_code: "+971", individual_mobile_number: "",
    individual_email: "", uae_visa_number: "", uae_visa_expiry: "", nature_of_services_sought: [],
  };

  const openNew = () => { setForm(BLANK); setModal("new"); setSectionStatus({}); setSectionError({}); };

  const openEdit = (a) => {
    setForm({
      account_type: a.account_type || "Corporate",
      company_name: a.company_name, industry: a.industry || "", country: a.country || "", strategic_priority: a.strategic_priority,
      existing_relationship: a.existing_relationship, key_contacts: a.key_contacts || "", single_point_of_contact: a.single_point_of_contact || "", website: a.website || "", spoc_id: a.spoc_id || "",
      anchor_entity: a.anchor_entity || "", non_anchor_entities: a.non_anchor_entities || [],
      registration_number: a.registration_number || "", incorporation_date: a.incorporation_date || "", license_number: a.license_number || "", risk_rating: a.risk_rating || "", kyc_status: a.kyc_status || "Not Started",
      licensing_authority: a.licensing_authority || "", license_start_date: a.license_start_date || "", license_expiry_date: a.license_expiry_date || "",
      is_regulated: !!a.is_regulated, regulator_name: a.regulator_name || "", regulator_other: a.regulator_other || "",
      license_category: a.license_category || "", license_activities: a.license_activities || "",
      registered_address: { ...BLANK_ADDRESS, ...(a.registered_address || {}) }, operating_address: { ...BLANK_ADDRESS, ...(a.operating_address || {}) },
      trn_vat_number: a.trn_vat_number || "", corp_tax_registered: !!a.corp_tax_registered, corp_tax_registration_number: a.corp_tax_registration_number || "",
      financial_year_end: a.financial_year_end || "", has_introducer: !!a.has_introducer, introducer_name: a.introducer_name || "",
      services_obtained: a.services_obtained || [], tags: a.tags ? a.tags.split(",").map((t) => t.trim()).filter(Boolean) : [],
      profile_status: a.profile_status || "New",
      engagement_letter_signed: !!a.engagement_letter_signed, engagement_letter_valid_until: a.engagement_letter_valid_until || "",
      aml_classification: a.aml_classification || "", edd_reason: a.edd_reason || "", cdd_completion_date: a.cdd_completion_date || "",
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
    });
    setModal("edit");
    setSectionStatus({});
    setSectionError({});
  };

  const deleteAccount = async (id) => {
    if (!confirm("Delete this client? This cannot be undone.")) return;
    try {
      await accountsApi.delete(id);
      setSelectedId(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to delete client");
    }
  };

  const toggleSelected = (id) => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const toggleSelectAllFiltered = (ids) => setSelectedIds((prev) =>
    ids.every((id) => prev.has(id)) ? new Set() : new Set(ids)
  );

  const applyBulkField = async (field) => {
    const value = bulkValues[field];
    if (!value || selectedIds.size === 0) return;
    setBulkApplying(true);
    try {
      const results = await accountsApi.bulkUpdate({ ids: [...selectedIds], [field]: field === "spoc_id" ? +value : value });
      const failed = results.filter((r) => r.status === "error");
      alert(failed.length === 0
        ? `Updated ${results.length} client${results.length !== 1 ? "s" : ""}.`
        : `Updated ${results.length - failed.length}/${results.length}. ${failed.length} failed (e.g. access denied).`);
      setSelectedIds(new Set());
      setBulkValues({ spoc_id: "", risk_rating: "", kyc_status: "" });
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Bulk update failed");
    } finally {
      setBulkApplying(false);
    }
  };

  // Empty-string optional date fields must become null (FastAPI can't parse "" as a date).
  const cleanPayload = (obj) => Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
  );

  const save = async () => {
    if (!form.company_name?.trim()) return alert("Company name is required");
    if (modal === "new" && form.account_type !== "Individual" && !form.industry?.trim()) return alert("Industry is required");
    try {
      setSaving(true);
      const { next_aml_review_date, tags, ...rest } = form;
      const payload = cleanPayload({ ...rest, tags: (tags || []).join(", ") || null });
      if (modal === "edit") {
        const { _id, ...patch } = payload;
        await accountsApi.update(_id, { ...patch, spoc_id: patch.spoc_id ? +patch.spoc_id : null });
      } else {
        await accountsApi.create({ ...payload, spoc_id: payload.spoc_id ? +payload.spoc_id : null });
      }
      setModal(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || (modal === "edit" ? "Failed to update client" : "Failed to create client"));
    } finally { setSaving(false); }
  };

  // Client CRM-change-request item 19 — per-section Save, so each section validates and
  // persists independently instead of only surfacing errors at the very bottom of the form.
  const [sectionStatus, setSectionStatus] = useState({});
  const [sectionError, setSectionError] = useState({});

  const buildSectionPatch = (fieldKeys) => {
    const picked = {};
    for (const k of fieldKeys) picked[k] = form[k];
    if ("tags" in picked) picked.tags = (picked.tags || []).join(", ") || null;
    const clean = cleanPayload(picked);
    if ("spoc_id" in clean) clean.spoc_id = clean.spoc_id ? +clean.spoc_id : null;
    return clean;
  };

  const saveSection = async (key, fieldKeys, isCore = false) => {
    setSectionStatus((s) => ({ ...s, [key]: "saving" }));
    setSectionError((s) => ({ ...s, [key]: null }));
    try {
      const patch = buildSectionPatch(fieldKeys);
      if (form._id) {
        const updated = await accountsApi.update(form._id, patch);
        setForm((f) => ({ ...f, next_aml_review_date: updated.next_aml_review_date }));
      } else {
        if (!isCore) throw { response: { data: { detail: "Save Client Info first." } } };
        if (!form.company_name?.trim()) throw { response: { data: { detail: "Company name is required" } } };
        if (form.account_type !== "Individual" && !form.industry?.trim()) throw { response: { data: { detail: "Industry is required" } } };
        const created = await accountsApi.create(patch);
        setForm((f) => ({ ...f, _id: created.id }));
        setModal("edit");
      }
      setSectionStatus((s) => ({ ...s, [key]: "saved" }));
      load();
      setTimeout(() => setSectionStatus((s) => (s[key] === "saved" ? { ...s, [key]: "idle" } : s)), 2500);
    } catch (e) {
      setSectionStatus((s) => ({ ...s, [key]: "error" }));
      setSectionError((s) => ({ ...s, [key]: e.response?.data?.detail || "Save failed" }));
    }
  };

  const CORE_FIELDS = [
    "account_type", "company_name", "industry", "country", "website", "key_contacts",
    "single_point_of_contact", "strategic_priority", "existing_relationship", "spoc_id",
    "anchor_entity", "non_anchor_entities", "registration_number", "license_number", "incorporation_date",
    "risk_rating", "kyc_status", "tags",
  ];
  const LICENSING_FIELDS = ["licensing_authority", "license_start_date", "license_expiry_date", "license_activities", "is_regulated", "regulator_name", "regulator_other", "license_category"];
  const REGISTERED_ADDRESS_FIELDS = ["registered_address"];
  const OPERATING_ADDRESS_FIELDS = ["operating_address"];
  const TAX_FIELDS = ["trn_vat_number", "financial_year_end", "corp_tax_registered", "corp_tax_registration_number"];
  const INDIVIDUAL_FIELDS = [
    "date_of_birth", "country_of_birth", "nationality", "passport_number", "passport_expiry_date", "occupation",
    "source_of_funds", "source_of_wealth", "country_of_residence", "residential_address",
    "individual_mobile_country_code", "individual_mobile_number", "individual_email",
    "uae_visa_number", "uae_visa_expiry", "nature_of_services_sought", "is_pep",
  ];
  const INTRODUCER_FIELDS = ["has_introducer", "introducer_name"];
  const SERVICES_FIELDS = ["services_obtained"];
  const PROFILE_STATUS_FIELDS = ["profile_status", "engagement_letter_valid_until", "engagement_letter_signed"];
  const AML_FIELDS = ["aml_classification", "cdd_completion_date", "edd_reason"];

  const ADDRESS_COLS = ["Line 1", "Line 2", "Landmark", "City", "ZIP", "P.O. Box", "Country"];
  const addrRow = (v) => { const a = v || {}; return [a.line1, a.line2, a.landmark, a.city, a.zip, a.po_box, a.country]; };

  const exportCSV = () => {
    const headers = [
      "Account UID", "Client Type", "Company Name", "Industry", "Country", "Website", "Key Contacts", "Single Point of Contact",
      "Anchor Entity", "Non-anchor Entities",
      "Strategic Priority", "Existing Relationship", "Tags", "Incorporation Certificate No.", "Incorporation Date", "License Number",
      "Risk Rating", "KYC Status", "SPOC",
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
    const rows = accounts.map((a) => [
      a.account_uid, a.account_type, a.company_name, a.industry, a.country, a.website, a.key_contacts, a.single_point_of_contact,
      a.anchor_entity, (a.non_anchor_entities || []).join("; "),
      a.strategic_priority, a.existing_relationship, a.tags, a.registration_number, a.incorporation_date, a.license_number,
      a.risk_rating, a.kyc_status, users.find((u) => u.id === a.spoc_id)?.name || "",
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
    const csv = [headers, ...rows].map((r) => r.map((v) => `"${(v ?? "").toString().replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "clients.csv"; a.click();
  };

  const handleImportFile = async (file) => {
    const text = await file.text();
    const parsed = parseCSV(text).filter((r) => r.company_name).map((row) => {
      const { __spoc_name, ...rest } = row;
      if (__spoc_name) {
        const match = users.find((u) => u.name.toLowerCase() === __spoc_name.toLowerCase());
        if (match) rest.spoc_id = match.id;
      }
      return rest;
    });
    if (parsed.length === 0) { alert("No rows with a Company Name found in that CSV."); return; }
    try {
      setImporting(true);
      const res = await accountsApi.import(parsed, true);
      setImportPreview({ rows: parsed, ...res });
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to preview import");
    } finally { setImporting(false); }
  };

  const confirmImport = async () => {
    if (!importPreview) return;
    try {
      setImporting(true);
      await accountsApi.import(importPreview.rows, false);
      setImportPreview(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Import failed");
    } finally { setImporting(false); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const filtered = accounts.filter((a) => search === "" || a.company_name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Clients</h1>
          <p className="text-sm text-gray-500">{accounts.length} clients · {fmt(accounts.reduce((s, a) => s + Number(a.total_invoiced_amount || 0), 0))} total invoiced</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={exportCSV} className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">Export CSV</button>
          {isAdmin && (
            <>
              <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ""; }} />
              <button onClick={() => fileInputRef.current?.click()} disabled={importing}
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-50">
                {importing ? "Reading..." : "Import CSV"}
              </button>
            </>
          )}
          <button onClick={openNew}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white rounded-lg font-medium"
            style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={15} /> New Client
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative max-w-md flex-1 min-w-[200px]">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search clients..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-brand-400" />
        </div>
        {filtered.length > 0 && (
          <label className="flex items-center gap-1.5 text-xs text-gray-500">
            <input type="checkbox" checked={filtered.every((a) => selectedIds.has(a.id))}
              onChange={() => toggleSelectAllFiltered(filtered.map((a) => a.id))} />
            Select all ({filtered.length})
          </label>
        )}
      </div>

      {selectedIds.size > 0 && (
        <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3 flex items-center flex-wrap gap-3">
          <span className="text-xs font-medium text-brand-700">{selectedIds.size} selected</span>
          <div className="flex items-center gap-1.5">
            <Select value={bulkValues.spoc_id} onChange={(e) => setBulkValues((p) => ({ ...p, spoc_id: e.target.value }))} className="text-xs">
              <option value="">SPOC…</option>
              {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </Select>
            <button disabled={!bulkValues.spoc_id || bulkApplying} onClick={() => applyBulkField("spoc_id")}
              className="px-2.5 py-1.5 text-xs border border-brand-300 rounded-lg bg-white hover:bg-brand-100 disabled:opacity-40">Apply</button>
          </div>
          <div className="flex items-center gap-1.5">
            <Select value={bulkValues.risk_rating} onChange={(e) => setBulkValues((p) => ({ ...p, risk_rating: e.target.value }))} className="text-xs">
              <option value="">Risk Rating…</option>
              {RISK_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </Select>
            <button disabled={!bulkValues.risk_rating || bulkApplying} onClick={() => applyBulkField("risk_rating")}
              className="px-2.5 py-1.5 text-xs border border-brand-300 rounded-lg bg-white hover:bg-brand-100 disabled:opacity-40">Apply</button>
          </div>
          <div className="flex items-center gap-1.5">
            <Select value={bulkValues.kyc_status} onChange={(e) => setBulkValues((p) => ({ ...p, kyc_status: e.target.value }))} className="text-xs">
              <option value="">KYC Status…</option>
              {KYC_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
            <button disabled={!bulkValues.kyc_status || bulkApplying} onClick={() => applyBulkField("kyc_status")}
              className="px-2.5 py-1.5 text-xs border border-brand-300 rounded-lg bg-white hover:bg-brand-100 disabled:opacity-40">Apply</button>
          </div>
          <button onClick={() => setSelectedIds(new Set())} className="text-xs text-brand-500 hover:underline ml-auto">Clear selection</button>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="text-center py-16 text-gray-400 text-sm">
          No clients yet. Click <strong>New Client</strong> to add your first client company.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((a) => {
          const isOpen = selectedId === a.id;
          const accountCases = cases.filter((c) => c.account_id === a.id);
          return (
            <div key={a.id}
              onClick={() => setSelectedId(isOpen ? null : a.id)}
              className={`bg-white border rounded-xl p-5 shadow-sm cursor-pointer hover:shadow-md transition-all ${isOpen ? "border-brand-400 ring-1 ring-brand-200" : "border-gray-100"}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <input type="checkbox" checked={selectedIds.has(a.id)} onClick={(e) => e.stopPropagation()}
                    onChange={() => toggleSelected(a.id)} className="mt-1 flex-shrink-0" />
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm"
                    style={{ background: "#1a3a5c" }}>
                    {a.company_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-800">{a.company_name}</h3>
                    <p className="text-xs text-gray-500">
                      {a.account_type === "Individual"
                        ? `${a.nationality || "—"} · ${a.occupation || "Individual"}`
                        : `${a.industry || "—"} · ${a.country || "—"}`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                  {a.account_type === "Individual" && <Badge text="Individual" />}
                  {a.is_pep && <Badge text="PEP" />}
                  {a.profile_status && a.profile_status !== "New" && <Badge text={a.profile_status} />}
                  <Badge text={a.strategic_priority} />
                  {a.risk_rating && <Badge text={`${a.risk_rating} Risk`} />}
                  <button onClick={() => openEdit(a)} title="Edit" className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600 ml-1">
                    <Icon name="edit" size={14} />
                  </button>
                  <button onClick={() => deleteAccount(a.id)} title="Delete" className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                    <Icon name="del" size={14} />
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-500">Invoiced</p>
                  <p className="text-sm font-bold text-gray-800">{fmt(a.total_invoiced_amount)}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-500">Cases</p>
                  <p className="text-sm font-bold text-gray-800">{a.total_cases}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-500">Existing</p>
                  <p className="text-sm font-bold text-gray-800">{a.existing_relationship}</p>
                </div>
              </div>
              {isOpen && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs font-semibold text-gray-600 mb-2">Key Contacts</p>
                  <p className="text-xs text-gray-600 mb-3">{a.key_contacts || "—"}</p>
                  <p className="text-xs font-semibold text-gray-600 mb-2">Compliance</p>
                  <div className="grid grid-cols-3 gap-3 text-center mb-3">
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">Reg. No.</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{a.registration_number || "—"}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">License No.</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{a.license_number || "—"}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">KYC Status</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{a.kyc_status || "—"}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">AML Class</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{a.aml_classification || "—"}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">Next AML Review</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{fmtDate(a.next_aml_review_date) || "—"}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">TRN/VAT</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{a.trn_vat_number || "—"}</p>
                    </div>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); setPartiesAccount(a); }}
                    className="w-full mb-2 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 flex items-center justify-center gap-1">
                    <Icon name="accounts" size={13} /> Manage Shareholders / Directors / Signatories
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); setTrackRecordAccount(a); }}
                    className="w-full mb-2 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 flex items-center justify-center gap-1">
                    <Icon name="download" size={13} /> Track Record
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); setAttachmentsAccount(a); }}
                    className="w-full mb-3 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 flex items-center justify-center gap-1">
                    <Icon name="instructions" size={13} /> Attachments
                  </button>
                  <p className="text-xs font-semibold text-gray-600 mb-2">Cases ({accountCases.length})</p>
                  <div className="space-y-1.5">
                    {accountCases.map((c) => (
                      <div key={c.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                        <div className="flex-1 min-w-0 mr-2">
                          <div className="text-xs font-medium text-gray-700 truncate">{c.case_uid}</div>
                          <Badge text={c.stage} />
                        </div>
                        <span className="text-xs font-bold" style={{ color: "#1a3a5c" }}>{fmt(c.invoice_amount)}</span>
                      </div>
                    ))}
                    {accountCases.length === 0 && <p className="text-xs text-gray-400">No cases yet.</p>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {modal && (
        <Modal title={modal === "edit" ? `Edit Client` : "New Client"} onClose={() => setModal(null)}>
          <div className="space-y-3">
            <Field label="Client Type">
              <Select value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value })}>
                <option>Corporate</option>
                <option>Individual</option>
              </Select>
            </Field>
            <Field label={form.account_type === "Individual" ? "Full Name (as per passport) *" : "Company Name *"}>
              <Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder={form.account_type === "Individual" ? "e.g. John Smith" : "e.g. Al Futtaim Group"} />
            </Field>
            <DuplicateWarning
              name={form.company_name}
              excludeId={form._id}
              checkFn={accountsApi.checkDuplicate}
              active={modal === "new"}
              onSelect={async (id) => { const existing = await accountsApi.get(id); openEdit(existing); }}
            />
            {form.account_type !== "Individual" && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Industry *">
                    <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} placeholder="e.g. Fintech" />
                  </Field>
                  <Field label="Country of Incorporation / Registration">
                    <CountrySelect value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} countries={countries} />
                  </Field>
                </div>
                <Field label="Website">
                  <Input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="e.g. https://company.com" />
                </Field>
              </>
            )}
            <Field label="Key Contacts">
              <Input value={form.key_contacts} onChange={(e) => setForm({ ...form, key_contacts: e.target.value })} placeholder="e.g. John Smith - CEO" />
            </Field>
            <Field label="Single Point of Contact (Client Contact Name)">
              <Input value={form.single_point_of_contact} onChange={(e) => setForm({ ...form, single_point_of_contact: e.target.value })} placeholder="e.g. Jane Doe" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Strategic Priority">
                <Select value={form.strategic_priority} onChange={(e) => setForm({ ...form, strategic_priority: e.target.value })}>
                  {PRIORITY_OPTIONS.map((p) => <option key={p}>{p}</option>)}
                </Select>
              </Field>
              <Field label="Existing Relationship">
                <Select value={form.existing_relationship} onChange={(e) => setForm({ ...form, existing_relationship: e.target.value })}>
                  <option>No</option>
                  <option>Yes</option>
                </Select>
              </Field>
            </div>
            <Field label="SPOC (Single Point of Contact)">
              <Select value={form.spoc_id || ""} onChange={(e) => setForm({ ...form, spoc_id: e.target.value })}>
                <option value="">— None —</option>
                {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Anchor Entity">
                <Select value={form.anchor_entity || ""} onChange={(e) => setForm({ ...form, anchor_entity: e.target.value, non_anchor_entities: (form.non_anchor_entities || []).filter((x) => x !== e.target.value) })}>
                  <option value="">— select —</option>
                  {TRIAM_ENTITY_OPTIONS.map((t) => <option key={t}>{t}</option>)}
                </Select>
              </Field>
              <Field label="Non-anchor Entities">
                <MultiSelect options={TRIAM_ENTITY_OPTIONS.filter((t) => t !== form.anchor_entity)} value={form.non_anchor_entities} onChange={(v) => setForm({ ...form, non_anchor_entities: v })} />
              </Field>
            </div>
            {form.account_type !== "Individual" && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Incorporation Certificate No.">
                  <Input value={form.registration_number} onChange={(e) => setForm({ ...form, registration_number: e.target.value })} placeholder="e.g. 123456" maxLength={30} />
                </Field>
                <Field label="License Number">
                  <Input value={form.license_number} onChange={(e) => setForm({ ...form, license_number: e.target.value })} placeholder="e.g. DIFC-LIC-9012" />
                </Field>
                <Field label="Incorporation Date">
                  <Input type="date" max={new Date().toISOString().slice(0, 10)} value={form.incorporation_date || ""} onChange={(e) => setForm({ ...form, incorporation_date: e.target.value })} />
                </Field>
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Risk Rating">
                <Select value={form.risk_rating || ""} onChange={(e) => setForm({ ...form, risk_rating: e.target.value })}>
                  <option value="">— Not set —</option>
                  {RISK_OPTIONS.map((r) => <option key={r}>{r}</option>)}
                </Select>
              </Field>
              <Field label="KYC Status">
                <Select value={form.kyc_status} onChange={(e) => setForm({ ...form, kyc_status: e.target.value })}>
                  {KYC_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Field>
            </div>

            <Field label="Tags">
              <MultiSelect options={TAG_OPTIONS} value={form.tags} onChange={(v) => setForm({ ...form, tags: v })} />
            </Field>

            <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100">
              <button type="button" onClick={() => saveSection("core", CORE_FIELDS, true)} disabled={sectionStatus.core === "saving"}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-50">
                {sectionStatus.core === "saving" ? "Saving…" : "Save Client Info"}
              </button>
              {sectionStatus.core === "saved" && <span className="text-xs text-emerald-600">Saved</span>}
              {sectionStatus.core === "error" && <span className="text-xs text-red-600">{sectionError.core || "Save failed"}</span>}
              {!form._id && <span className="text-xs text-gray-400">Save this first to unlock the sections below</span>}
            </div>

            {form.account_type !== "Individual" && (
              <>
                <Section title="Licensing & Regulatory" hasData={!!(form.licensing_authority || form.license_activities || form.license_start_date || form.license_expiry_date || form.is_regulated || form.license_category)}
                  onSave={() => saveSection("licensing", LICENSING_FIELDS)} status={sectionStatus.licensing} error={sectionError.licensing}>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Licensing Authority">
                      <Input value={form.licensing_authority} onChange={(e) => setForm({ ...form, licensing_authority: e.target.value })} placeholder="e.g. DIFC, ADGM, DED" />
                    </Field>
                    <Field label="License Start Date"><Input type="date" value={form.license_start_date || ""} onChange={(e) => setForm({ ...form, license_start_date: e.target.value })} /></Field>
                    <Field label="License Expiry Date"><Input type="date" min={new Date().toISOString().slice(0, 10)} value={form.license_expiry_date || ""} onChange={(e) => setForm({ ...form, license_expiry_date: e.target.value })} /></Field>
                  </div>
                  <div className="mb-3">
                    <Field label="License Activities">
                      <Textarea rows={3} value={form.license_activities} onChange={(e) => setForm({ ...form, license_activities: e.target.value })} />
                    </Field>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                    <input type="checkbox" checked={!!form.is_regulated} onChange={(e) => setForm({ ...form, is_regulated: e.target.checked })} /> Is entity regulated
                  </label>
                  {form.is_regulated && (
                    <div className="grid grid-cols-2 gap-3">
                      <Field label="Regulator">
                        <Select value={form.regulator_name || ""} onChange={(e) => setForm({ ...form, regulator_name: e.target.value })}>
                          <option value="">— select —</option>
                          {REGULATOR_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                        </Select>
                      </Field>
                      {form.regulator_name === "Other" && (
                        <Field label="Other Regulator"><Input value={form.regulator_other} onChange={(e) => setForm({ ...form, regulator_other: e.target.value })} /></Field>
                      )}
                      <Field label="License Category"><Input value={form.license_category} onChange={(e) => setForm({ ...form, license_category: e.target.value })} /></Field>
                    </div>
                  )}
                </Section>

                <Section title="Registered Address" hasData={Object.values(form.registered_address || {}).some(Boolean)}
                  onSave={() => saveSection("registeredAddress", REGISTERED_ADDRESS_FIELDS)} status={sectionStatus.registeredAddress} error={sectionError.registeredAddress}>
                  <AddressFields value={form.registered_address} onChange={(v) => setForm({ ...form, registered_address: v })} />
                </Section>

                <Section title="Operating Address" hasData={Object.values(form.operating_address || {}).some(Boolean)}
                  onSave={() => saveSection("operatingAddress", OPERATING_ADDRESS_FIELDS)} status={sectionStatus.operatingAddress} error={sectionError.operatingAddress}>
                  <AddressFields value={form.operating_address} onChange={(v) => setForm({ ...form, operating_address: v })} />
                </Section>

                <Section title="Tax" hasData={!!(form.trn_vat_number || form.financial_year_end || form.corp_tax_registered)}
                  onSave={() => saveSection("tax", TAX_FIELDS)} status={sectionStatus.tax} error={sectionError.tax}>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="TRN / VAT Registration No."><Input value={form.trn_vat_number} onChange={(e) => setForm({ ...form, trn_vat_number: e.target.value })} maxLength={15} /></Field>
                    <Field label="Financial Year End (MM-DD)"><Input value={form.financial_year_end} onChange={(e) => setForm({ ...form, financial_year_end: e.target.value })} placeholder="12-31" /></Field>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                    <input type="checkbox" checked={!!form.corp_tax_registered} onChange={(e) => setForm({ ...form, corp_tax_registered: e.target.checked })} /> Corporate Tax Registered
                  </label>
                  {form.corp_tax_registered && (
                    <Field label="Corp Tax Registration No. / TAN"><Input value={form.corp_tax_registration_number} onChange={(e) => setForm({ ...form, corp_tax_registration_number: e.target.value })} maxLength={15} /></Field>
                  )}
                </Section>
              </>
            )}

            {form.account_type === "Individual" && (
              <Section title="Individual Details" hasData={!!(form.date_of_birth || form.country_of_birth || form.nationality || form.passport_number || form.occupation || form.individual_mobile_number || form.individual_email || form.country_of_residence || form.source_of_funds || form.source_of_wealth || form.is_pep || (form.nature_of_services_sought || []).length > 0)}
                onSave={() => saveSection("individual", INDIVIDUAL_FIELDS)} status={sectionStatus.individual} error={sectionError.individual}>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Date of Birth"><Input type="date" value={form.date_of_birth || ""} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} /></Field>
                  <Field label="Country of Birth"><CountrySelect value={form.country_of_birth} onChange={(e) => setForm({ ...form, country_of_birth: e.target.value })} countries={countries} /></Field>
                  <Field label="Nationality"><CountrySelect value={form.nationality} onChange={(e) => setForm({ ...form, nationality: e.target.value })} countries={countries} /></Field>
                  <Field label="Passport Number"><Input value={form.passport_number} onChange={(e) => setForm({ ...form, passport_number: e.target.value })} /></Field>
                  <Field label="Passport Expiry"><Input type="date" value={form.passport_expiry_date || ""} onChange={(e) => setForm({ ...form, passport_expiry_date: e.target.value })} /></Field>
                  <Field label="Occupation"><Input value={form.occupation} onChange={(e) => setForm({ ...form, occupation: e.target.value })} /></Field>
                  <Field label="Email"><Input type="email" value={form.individual_email} onChange={(e) => setForm({ ...form, individual_email: e.target.value })} /></Field>
                  <Field label="Country of Residence"><CountrySelect value={form.country_of_residence} onChange={(e) => setForm({ ...form, country_of_residence: e.target.value })} countries={countries} /></Field>
                </div>
                <Field label="Mobile">
                  <div className="flex gap-2">
                    <Select value={form.individual_mobile_country_code || ""} onChange={(e) => setForm({ ...form, individual_mobile_country_code: e.target.value })} className="w-40 flex-shrink-0">
                      <option value="">Code</option>
                      {COUNTRY_CALLING_CODES.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                    </Select>
                    <Input value={form.individual_mobile_number || ""} onChange={(e) => setForm({ ...form, individual_mobile_number: e.target.value })} maxLength={12} placeholder="e.g. 501234567" />
                  </div>
                </Field>
                <Field label="Source of Funds"><Input value={form.source_of_funds} onChange={(e) => setForm({ ...form, source_of_funds: e.target.value })} placeholder="e.g. Salary, business income" /></Field>
                <Field label="Source of Wealth"><Input value={form.source_of_wealth} onChange={(e) => setForm({ ...form, source_of_wealth: e.target.value })} placeholder="e.g. Accumulated savings, inheritance" /></Field>
                <Field label="Nature of Services Sought">
                  <MultiSelect options={SERVICES_OBTAINED_OPTIONS} value={form.nature_of_services_sought} onChange={(v) => setForm({ ...form, nature_of_services_sought: v })} />
                </Field>

                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1.5">Residential Address</p>
                <AddressFields value={form.residential_address} onChange={(v) => setForm({ ...form, residential_address: v })} />

                {form.country_of_residence === "UAE" && (
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <Field label="UAE Visa No."><Input value={form.uae_visa_number} onChange={(e) => setForm({ ...form, uae_visa_number: e.target.value })} /></Field>
                    <Field label="UAE Visa Expiry"><Input type="date" value={form.uae_visa_expiry || ""} onChange={(e) => setForm({ ...form, uae_visa_expiry: e.target.value })} /></Field>
                  </div>
                )}

                <label className="flex items-center gap-2 text-xs text-gray-700 mt-3">
                  <input type="checkbox" checked={!!form.is_pep} onChange={(e) => setForm({ ...form, is_pep: e.target.checked })} /> Politically Exposed Person (PEP)
                </label>
              </Section>
            )}

            <Section title="Introducer" hasData={!!form.has_introducer}
              onSave={() => saveSection("introducer", INTRODUCER_FIELDS)} status={sectionStatus.introducer} error={sectionError.introducer}>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                <input type="checkbox" checked={!!form.has_introducer} onChange={(e) => setForm({ ...form, has_introducer: e.target.checked })} /> Introduced by a third party
              </label>
              {form.has_introducer && (
                <Field label="Introducer Name"><Input value={form.introducer_name} onChange={(e) => setForm({ ...form, introducer_name: e.target.value })} /></Field>
              )}
            </Section>

            <Section title="Services Obtained" hasData={(form.services_obtained || []).length > 0}
              onSave={() => saveSection("services", SERVICES_FIELDS)} status={sectionStatus.services} error={sectionError.services}>
              <MultiSelect options={SERVICES_OBTAINED_OPTIONS} value={form.services_obtained} onChange={(v) => setForm({ ...form, services_obtained: v })} />
            </Section>

            <Section title="Profile Status & Engagement" hasData={form.profile_status !== "New" || !!form.engagement_letter_signed || !!form.engagement_letter_valid_until}
              onSave={() => saveSection("profileStatus", PROFILE_STATUS_FIELDS)} status={sectionStatus.profileStatus} error={sectionError.profileStatus}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Profile Status">
                  <Select value={form.profile_status} onChange={(e) => setForm({ ...form, profile_status: e.target.value })}>
                    {PROFILE_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
                  </Select>
                </Field>
                <Field label="Engagement Letter Valid Until"><Input type="date" value={form.engagement_letter_valid_until || ""} onChange={(e) => setForm({ ...form, engagement_letter_valid_until: e.target.value })} /></Field>
              </div>
              <label className="flex items-center gap-2 text-xs text-gray-700">
                <input type="checkbox" checked={!!form.engagement_letter_signed} onChange={(e) => setForm({ ...form, engagement_letter_signed: e.target.checked })} /> Engagement Letter Signed
              </label>
            </Section>

            <Section title="AML Classification" hasData={!!(form.aml_classification || form.cdd_completion_date)}
              onSave={() => saveSection("aml", AML_FIELDS)} status={sectionStatus.aml} error={sectionError.aml}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="AML Classification">
                  <Select value={form.aml_classification || ""} onChange={(e) => setForm({ ...form, aml_classification: e.target.value })}>
                    <option value="">— select —</option>
                    {AML_CLASSIFICATION_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </Select>
                </Field>
                <Field label="CDD Completion Date"><Input type="date" value={form.cdd_completion_date || ""} onChange={(e) => setForm({ ...form, cdd_completion_date: e.target.value })} /></Field>
              </div>
              {form.aml_classification === "EDD" && (
                <Field label="Reason for EDD"><Input value={form.edd_reason} onChange={(e) => setForm({ ...form, edd_reason: e.target.value })} maxLength={25} /></Field>
              )}
              {form.next_aml_review_date && (
                <p className="text-xs text-gray-400">Next AML Review Date: <span className="font-medium text-gray-600">{fmtDate(form.next_aml_review_date)}</span> (auto-calculated from Risk Rating + CDD Completion Date)</p>
              )}
            </Section>
          </div>
          <div className="flex justify-end gap-3 mt-5">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} disabled={saving}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
              style={{ background: "#1a3a5c" }}>
              {saving ? "Saving..." : modal === "edit" ? "Save Changes" : "Create Client"}
            </button>
          </div>
        </Modal>
      )}

      {importPreview && (
        <Modal title="Import Clients — Preview" onClose={() => setImportPreview(null)}>
          <p className="text-sm text-gray-600 mb-3">
            {importPreview.results.filter((r) => r.status === "ok").length} of {importPreview.results.length} rows will be created.
            {" "}{importPreview.results.filter((r) => r.status === "duplicate").length} duplicate(s), {" "}
            {importPreview.results.filter((r) => r.status === "error").length} error(s) will be skipped.
          </p>
          <div className="max-h-80 overflow-y-auto border border-gray-100 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left p-2 font-semibold text-gray-600">Row</th>
                  <th className="text-left p-2 font-semibold text-gray-600">Company Name</th>
                  <th className="text-left p-2 font-semibold text-gray-600">Status</th>
                  <th className="text-left p-2 font-semibold text-gray-600">Note</th>
                </tr>
              </thead>
              <tbody>
                {importPreview.results.map((r) => (
                  <tr key={r.row_index} className="border-t border-gray-100">
                    <td className="p-2 text-gray-400">{r.row_index + 1}</td>
                    <td className="p-2 text-gray-700">{r.company_name || "—"}</td>
                    <td className="p-2">
                      {r.status === "ok" && <span className="text-emerald-600 font-medium">Will create</span>}
                      {r.status === "duplicate" && <span className="text-amber-600 font-medium">Duplicate</span>}
                      {r.status === "error" && <span className="text-red-600 font-medium">Error</span>}
                    </td>
                    <td className="p-2 text-gray-400">{r.message || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end gap-3 mt-5">
            <button onClick={() => setImportPreview(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={confirmImport} disabled={importing || !importPreview.results.some((r) => r.status === "ok")}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
              style={{ background: "#1a3a5c" }}>
              {importing ? "Importing..." : `Import ${importPreview.results.filter((r) => r.status === "ok").length} Client(s)`}
            </button>
          </div>
        </Modal>
      )}

      {partiesAccount && (
        <AccountPartyModal account={partiesAccount} onClose={() => { setPartiesAccount(null); load(); }} />
      )}

      {trackRecordAccount && (
        <TrackRecordModal account={trackRecordAccount} onClose={() => setTrackRecordAccount(null)} />
      )}

      {attachmentsAccount && (
        <Modal title={`Attachments — ${attachmentsAccount.company_name}`} onClose={() => setAttachmentsAccount(null)}>
          <DocumentsPanel accountId={attachmentsAccount.id} />
        </Modal>
      )}
    </div>
  );
}
