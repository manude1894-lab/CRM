import React, { useEffect, useRef, useState } from "react";
import { accountsApi, casesApi, usersApi, amlApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, MultiSelect, CountrySelect, Spinner, ErrorBanner } from "../components/ui";
import AccountPartyModal from "../components/AccountPartyModal";
import DuplicateWarning from "../components/DuplicateWarning";
import {
  fmt, REGULATOR_OPTIONS, TAG_OPTIONS, SERVICES_OBTAINED_OPTIONS,
  PROFILE_STATUS_OPTIONS, AML_CLASSIFICATION_OPTIONS,
} from "../utils/constants";
import { useAuthStore } from "../store/auth";

const PRIORITY_OPTIONS = ["Low", "Medium", "High"];
const RISK_OPTIONS = ["Low", "Medium", "High"];
const KYC_STATUS_OPTIONS = ["Not Started", "Submitted", "Under Review", "Approved", "Rejected"];

const BLANK_ADDRESS = { line1: "", line2: "", landmark: "", zip: "", po_box: "", city: "", country: "" };

const Section = ({ title, children }) => (
  <div className="mb-1">
    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">{title}</p>
    {children}
  </div>
);

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

const IMPORT_HEADER_MAP = {
  "company name": "company_name",
  "industry": "industry",
  "country": "country",
  "website": "website",
  "key contacts": "key_contacts",
  "strategic priority": "strategic_priority",
  "existing relationship": "existing_relationship",
  "registration number": "registration_number",
  "license number": "license_number",
  "risk rating": "risk_rating",
  "kyc status": "kyc_status",
};

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
      if (key) obj[key] = (r[i] || "").trim();
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
    key_contacts: "", website: "", spoc_id: "", registration_number: "", license_number: "", risk_rating: "", kyc_status: "Not Started",
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
    date_of_birth: "", nationality: "", passport_number: "", passport_expiry_date: "", occupation: "",
    source_of_funds: "", source_of_wealth: "", country_of_residence: "",
    residential_address: { ...BLANK_ADDRESS },
    individual_mobile: "", individual_email: "", uae_visa_number: "", uae_visa_expiry: "",
  };

  const openNew = () => { setForm(BLANK); setModal("new"); };

  const openEdit = (a) => {
    setForm({
      account_type: a.account_type || "Corporate",
      company_name: a.company_name, industry: a.industry || "", country: a.country || "", strategic_priority: a.strategic_priority,
      existing_relationship: a.existing_relationship, key_contacts: a.key_contacts || "", website: a.website || "", spoc_id: a.spoc_id || "",
      registration_number: a.registration_number || "", license_number: a.license_number || "", risk_rating: a.risk_rating || "", kyc_status: a.kyc_status || "Not Started",
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
      date_of_birth: a.date_of_birth || "", nationality: a.nationality || "", passport_number: a.passport_number || "",
      passport_expiry_date: a.passport_expiry_date || "", occupation: a.occupation || "",
      source_of_funds: a.source_of_funds || "", source_of_wealth: a.source_of_wealth || "", country_of_residence: a.country_of_residence || "",
      residential_address: { ...BLANK_ADDRESS, ...(a.residential_address || {}) },
      individual_mobile: a.individual_mobile || "", individual_email: a.individual_email || "",
      uae_visa_number: a.uae_visa_number || "", uae_visa_expiry: a.uae_visa_expiry || "",
      _id: a.id,
    });
    setModal("edit");
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

  // Empty-string optional date fields must become null (FastAPI can't parse "" as a date).
  const cleanPayload = (obj) => Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
  );

  const save = async () => {
    if (!form.company_name?.trim()) return alert("Company name is required");
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

  const exportCSV = () => {
    const headers = ["Company Name", "Industry", "Country", "Website", "Key Contacts", "Strategic Priority", "Existing Relationship", "Registration Number", "License Number", "Risk Rating", "KYC Status"];
    const rows = accounts.map((a) => [a.company_name, a.industry, a.country, a.website, a.key_contacts, a.strategic_priority, a.existing_relationship, a.registration_number, a.license_number, a.risk_rating, a.kyc_status]);
    const csv = [headers, ...rows].map((r) => r.map((v) => `"${(v ?? "").toString().replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "clients.csv"; a.click();
  };

  const handleImportFile = async (file) => {
    const text = await file.text();
    const parsed = parseCSV(text).filter((r) => r.company_name);
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
            style={{ background: "#2B6D9A" }}>
            <Icon name="plus" size={15} /> New Client
          </button>
        </div>
      </div>

      <div className="relative max-w-md">
        <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search clients..."
          className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-400" />
      </div>

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
              className={`bg-white border rounded-xl p-5 shadow-sm cursor-pointer hover:shadow-md transition-all ${isOpen ? "border-blue-400 ring-1 ring-blue-200" : "border-gray-100"}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm"
                    style={{ background: "#2B6D9A" }}>
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
                  <button onClick={() => openEdit(a)} title="Edit" className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600 ml-1">
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
                      <p className="text-xs font-bold text-gray-800 truncate">{a.next_aml_review_date || "—"}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-xs text-gray-500">TRN/VAT</p>
                      <p className="text-xs font-bold text-gray-800 truncate">{a.trn_vat_number || "—"}</p>
                    </div>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); setPartiesAccount(a); }}
                    className="w-full mb-3 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 flex items-center justify-center gap-1">
                    <Icon name="accounts" size={13} /> Manage Shareholders / Directors / Signatories
                  </button>
                  <p className="text-xs font-semibold text-gray-600 mb-2">Cases ({accountCases.length})</p>
                  <div className="space-y-1.5">
                    {accountCases.map((c) => (
                      <div key={c.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                        <div className="flex-1 min-w-0 mr-2">
                          <div className="text-xs font-medium text-gray-700 truncate">{c.case_uid}</div>
                          <Badge text={c.stage} />
                        </div>
                        <span className="text-xs font-bold" style={{ color: "#2B6D9A" }}>{fmt(c.invoice_amount)}</span>
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
            <DuplicateWarning name={form.company_name} excludeId={form._id} checkFn={accountsApi.checkDuplicate} active={modal === "new"} />
            {form.account_type !== "Individual" && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Industry">
                    <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} placeholder="e.g. Fintech" />
                  </Field>
                  <Field label="Country">
                    <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} placeholder="e.g. UAE" />
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
            {form.account_type !== "Individual" && (
              <div className="grid grid-cols-2 gap-3">
                <Field label="Registration Number">
                  <Input value={form.registration_number} onChange={(e) => setForm({ ...form, registration_number: e.target.value })} placeholder="e.g. 123456" />
                </Field>
                <Field label="License Number">
                  <Input value={form.license_number} onChange={(e) => setForm({ ...form, license_number: e.target.value })} placeholder="e.g. DIFC-LIC-9012" />
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

            {form.account_type !== "Individual" && (
              <>
                <Section title="Licensing & Regulatory">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Licensing Authority">
                      <Input value={form.licensing_authority} onChange={(e) => setForm({ ...form, licensing_authority: e.target.value })} placeholder="e.g. DIFC, ADGM, DED" />
                    </Field>
                    <Field label="License Activities">
                      <Input value={form.license_activities} onChange={(e) => setForm({ ...form, license_activities: e.target.value })} />
                    </Field>
                    <Field label="License Start Date"><Input type="date" value={form.license_start_date || ""} onChange={(e) => setForm({ ...form, license_start_date: e.target.value })} /></Field>
                    <Field label="License Expiry Date"><Input type="date" value={form.license_expiry_date || ""} onChange={(e) => setForm({ ...form, license_expiry_date: e.target.value })} /></Field>
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

                <Section title="Registered Address">
                  <AddressFields value={form.registered_address} onChange={(v) => setForm({ ...form, registered_address: v })} />
                </Section>

                <Section title="Operating Address">
                  <AddressFields value={form.operating_address} onChange={(v) => setForm({ ...form, operating_address: v })} />
                </Section>

                <Section title="Tax">
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="TRN / VAT Registration No."><Input value={form.trn_vat_number} onChange={(e) => setForm({ ...form, trn_vat_number: e.target.value })} /></Field>
                    <Field label="Financial Year End (MM-DD)"><Input value={form.financial_year_end} onChange={(e) => setForm({ ...form, financial_year_end: e.target.value })} placeholder="12-31" /></Field>
                  </div>
                  <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                    <input type="checkbox" checked={!!form.corp_tax_registered} onChange={(e) => setForm({ ...form, corp_tax_registered: e.target.checked })} /> Corporate Tax Registered
                  </label>
                  {form.corp_tax_registered && (
                    <Field label="Corp Tax Registration No. / TAN"><Input value={form.corp_tax_registration_number} onChange={(e) => setForm({ ...form, corp_tax_registration_number: e.target.value })} /></Field>
                  )}
                </Section>
              </>
            )}

            {form.account_type === "Individual" && (
              <Section title="Individual Details">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Date of Birth"><Input type="date" value={form.date_of_birth || ""} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} /></Field>
                  <Field label="Nationality"><CountrySelect value={form.nationality} onChange={(e) => setForm({ ...form, nationality: e.target.value })} countries={countries} /></Field>
                  <Field label="Passport Number"><Input value={form.passport_number} onChange={(e) => setForm({ ...form, passport_number: e.target.value })} /></Field>
                  <Field label="Passport Expiry"><Input type="date" value={form.passport_expiry_date || ""} onChange={(e) => setForm({ ...form, passport_expiry_date: e.target.value })} /></Field>
                  <Field label="Occupation"><Input value={form.occupation} onChange={(e) => setForm({ ...form, occupation: e.target.value })} /></Field>
                  <Field label="Mobile"><Input value={form.individual_mobile} onChange={(e) => setForm({ ...form, individual_mobile: e.target.value })} /></Field>
                  <Field label="Email"><Input type="email" value={form.individual_email} onChange={(e) => setForm({ ...form, individual_email: e.target.value })} /></Field>
                  <Field label="Country of Residence"><CountrySelect value={form.country_of_residence} onChange={(e) => setForm({ ...form, country_of_residence: e.target.value })} countries={countries} /></Field>
                </div>
                <Field label="Source of Funds"><Input value={form.source_of_funds} onChange={(e) => setForm({ ...form, source_of_funds: e.target.value })} placeholder="e.g. Salary, business income" /></Field>
                <Field label="Source of Wealth"><Input value={form.source_of_wealth} onChange={(e) => setForm({ ...form, source_of_wealth: e.target.value })} placeholder="e.g. Accumulated savings, inheritance" /></Field>

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

            <Section title="Introducer">
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                <input type="checkbox" checked={!!form.has_introducer} onChange={(e) => setForm({ ...form, has_introducer: e.target.checked })} /> Introduced by a third party
              </label>
              {form.has_introducer && (
                <Field label="Introducer Name"><Input value={form.introducer_name} onChange={(e) => setForm({ ...form, introducer_name: e.target.value })} /></Field>
              )}
            </Section>

            <Section title="Services Obtained">
              <MultiSelect options={SERVICES_OBTAINED_OPTIONS} value={form.services_obtained} onChange={(v) => setForm({ ...form, services_obtained: v })} />
            </Section>

            <Section title="Profile Status & Engagement">
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

            <Section title="AML Classification">
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
                <Field label="Reason for EDD"><Input value={form.edd_reason} onChange={(e) => setForm({ ...form, edd_reason: e.target.value })} maxLength={255} /></Field>
              )}
              {form.next_aml_review_date && (
                <p className="text-xs text-gray-400">Next AML Review Date: <span className="font-medium text-gray-600">{form.next_aml_review_date}</span> (auto-calculated from Risk Rating + CDD Completion Date)</p>
              )}
            </Section>
          </div>
          <div className="flex justify-end gap-3 mt-5">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} disabled={saving}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
              style={{ background: "#2B6D9A" }}>
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
              style={{ background: "#2B6D9A" }}>
              {importing ? "Importing..." : `Import ${importPreview.results.filter((r) => r.status === "ok").length} Client(s)`}
            </button>
          </div>
        </Modal>
      )}

      {partiesAccount && (
        <AccountPartyModal account={partiesAccount} onClose={() => { setPartiesAccount(null); load(); }} />
      )}
    </div>
  );
}
