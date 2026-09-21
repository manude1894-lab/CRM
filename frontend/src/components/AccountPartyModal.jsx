import React, { useEffect, useState } from "react";
import { accountPartiesApi, amlApi } from "../api/endpoints";
import { Icon, Modal, Field, Input, Select, CountrySelect, Spinner, ErrorBanner } from "./ui";
import { COUNTRY_CALLING_CODES } from "../utils/constants";

const ROLES = ["Shareholder", "Director", "Authorised Signatory"];

const BLANK_ADDRESS = { line1: "", line2: "", landmark: "", zip: "", po_box: "", city: "", country: "" };

const emptyParty = (role) => ({
  party_role: role,
  constitution: "Individual",
  full_name: "",
  dob_or_incorp_date: "",
  id_or_license_expiry: "",
  country_of_incorp_or_birth: "",
  mobile_country_code: "+971",
  mobile_number: "",
  email: "",
  country_of_residence: "",
  residential_address: { ...BLANK_ADDRESS },
  uae_visa_number: "",
  uae_visa_expiry: "",
  is_pep: false,
  effective_ownership_percent: "",
  nominee_director_name: "",
  notes: "",
});

// Strip blank-string fields to null so optional date/number columns don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

const partyLabel = (role) => role === "Shareholder" ? "Shareholder" : role === "Director" ? "Director" : "Authorised Signatory";

export default function AccountPartyModal({ account, onClose }) {
  const [tab, setTab] = useState("Shareholder");
  const [parties, setParties] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | "new" | row id
  const [form, setForm] = useState(null);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [ps, cs] = await Promise.all([
        accountPartiesApi.list(account.id),
        amlApi.countryRisk().catch(() => []),
      ]);
      setParties(ps || []);
      setCountries(cs || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load parties");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [account.id]);

  const startNew = () => { setForm(emptyParty(tab)); setEditing("new"); };
  const startEdit = (row) => { setForm({ ...row, residential_address: { ...BLANK_ADDRESS, ...(row.residential_address || {}) } }); setEditing(row.id); };
  const cancelForm = () => { setEditing(null); setForm(null); };

  const save = async () => {
    if (!form.full_name?.trim()) return alert("Full Name is required");
    try {
      const payload = cleanPayload(form);
      if (editing === "new") await accountPartiesApi.create(account.id, payload);
      else await accountPartiesApi.update(editing, payload);
      cancelForm();
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (row) => {
    if (!confirm(`Remove ${row.full_name}?`)) return;
    try { await accountPartiesApi.delete(row.id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  const switchTab = (t) => { setTab(t); cancelForm(); };

  const rowsForTab = parties.filter((p) => p.party_role === tab);
  const ownershipTotal = parties
    .filter((p) => p.party_role === "Shareholder")
    .reduce((s, p) => s + Number(p.effective_ownership_percent || 0), 0);

  return (
    <Modal title={`Parties — ${account.company_name}`} onClose={onClose}>
      <div className="flex border-b border-gray-100 mb-4 -mt-2">
        {ROLES.map((r) => (
          <button key={r} onClick={() => switchTab(r)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${tab === r ? "border-brand-500 text-brand-600" : "border-transparent text-gray-400 hover:text-gray-600"}`}>
            {partyLabel(r)} ({parties.filter((p) => p.party_role === r).length})
          </button>
        ))}
      </div>

      {tab === "Shareholder" && !editing && (
        <p className={`text-xs mb-2 ${ownershipTotal === 100 ? "text-gray-400" : "text-amber-600 font-medium"}`}>
          Total effective ownership: {ownershipTotal.toFixed(2)}%{ownershipTotal !== 100 && " (should total 100%)"}
        </p>
      )}

      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <>
          {!editing && (
            <>
              <div className="space-y-2 mb-3">
                {rowsForTab.length === 0
                  ? <p className="text-sm text-gray-400 text-center py-6">No {partyLabel(tab).toLowerCase()}s on record.</p>
                  : rowsForTab.map((p) => (
                    <div key={p.id} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          {p.full_name}
                          {p.is_pep && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">PEP</span>}
                          {p.nominee_director_name && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">Nominee: {p.nominee_director_name}</span>}
                        </div>
                        <div className="text-xs text-gray-400">
                          {p.constitution}
                          {p.country_of_incorp_or_birth && ` · ${p.country_of_incorp_or_birth}`}
                          {p.party_role === "Shareholder" && p.effective_ownership_percent != null && ` · ${p.effective_ownership_percent}% ownership`}
                          {p.country_of_residence && ` · resides ${p.country_of_residence}`}
                        </div>
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => startEdit(p)} className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600"><Icon name="edit" size={14} /></button>
                        <button onClick={() => remove(p)} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={14} /></button>
                      </div>
                    </div>
                  ))}
              </div>
              <button onClick={startNew} className="w-full px-3 py-2 text-xs border border-dashed border-gray-300 rounded-lg hover:border-brand-300 hover:text-brand-600 text-gray-500 flex items-center justify-center gap-1">
                <Icon name="plus" size={13} /> Add {partyLabel(tab)}
              </button>
            </>
          )}

          {editing && (
            <PartyForm form={form} setForm={setForm} countries={countries} onCancel={cancelForm} onSave={save} />
          )}
        </>
      )}
    </Modal>
  );
}

const set = (setForm, k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
const setBool = (setForm, k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));
const setAddr = (setForm, k) => (e) => setForm((p) => ({ ...p, residential_address: { ...p.residential_address, [k]: e.target.value } }));

function PartyForm({ form, setForm, countries, onCancel, onSave }) {
  const isShareholder = form.party_role === "Shareholder";
  const isDirector = form.party_role === "Director";
  const isEntity = form.constitution === "Entity";
  const isUAEResident = form.country_of_residence === "UAE";

  return (
    <div>
      {form.party_role !== "Authorised Signatory" && (
        <Field label="Constitution">
          <Select value={form.constitution} onChange={set(setForm, "constitution")}>
            <option>Individual</option>
            <option>Entity</option>
          </Select>
        </Field>
      )}
      <Field label={isEntity ? "Entity Name (as per license)" : "Full Name (as per passport)"} required>
        <Input value={form.full_name || ""} onChange={set(setForm, "full_name")} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={isEntity ? "Incorporation Date" : "Date of Birth"}>
          <Input type="date" value={form.dob_or_incorp_date || ""} onChange={set(setForm, "dob_or_incorp_date")} />
        </Field>
        <Field label={isEntity ? "License / CI Expiry" : "Passport Expiry"}>
          <Input type="date" value={form.id_or_license_expiry || ""} onChange={set(setForm, "id_or_license_expiry")} />
        </Field>
      </div>
      <Field label={isEntity ? "Country of Incorporation" : "Country of Birth"}>
        <CountrySelect value={form.country_of_incorp_or_birth} onChange={set(setForm, "country_of_incorp_or_birth")} countries={countries} />
      </Field>

      {isDirector && (
        <Field label="Nominee Director's Name (if applicable)">
          <Input value={form.nominee_director_name || ""} onChange={set(setForm, "nominee_director_name")} />
        </Field>
      )}
      {isShareholder && (
        <Field label="Effective Ownership Share (%)">
          <Input type="number" min="0" max="100" step="0.01" value={form.effective_ownership_percent ?? ""} onChange={set(setForm, "effective_ownership_percent")} />
        </Field>
      )}

      <Field label="Contact Mobile">
        <div className="flex gap-2">
          <Select value={form.mobile_country_code || ""} onChange={set(setForm, "mobile_country_code")} className="w-40 flex-shrink-0">
            <option value="">Code</option>
            {COUNTRY_CALLING_CODES.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
          </Select>
          <Input value={form.mobile_number || ""} onChange={set(setForm, "mobile_number")} maxLength={12} placeholder="e.g. 501234567" />
        </div>
      </Field>
      <Field label="Contact Email"><Input type="email" value={form.email || ""} onChange={set(setForm, "email")} /></Field>

      <Field label="Country of Residence">
        <CountrySelect value={form.country_of_residence} onChange={set(setForm, "country_of_residence")} countries={countries} />
      </Field>

      {form.country_of_residence && (
        <>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1">Residential Address</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Address Line 1"><Input value={form.residential_address?.line1 || ""} onChange={setAddr(setForm, "line1")} /></Field>
            <Field label="Address Line 2"><Input value={form.residential_address?.line2 || ""} onChange={setAddr(setForm, "line2")} /></Field>
            <Field label="Landmark"><Input value={form.residential_address?.landmark || ""} onChange={setAddr(setForm, "landmark")} /></Field>
            <Field label="City"><Input value={form.residential_address?.city || ""} onChange={setAddr(setForm, "city")} /></Field>
            <Field label="ZIP Code"><Input value={form.residential_address?.zip || ""} onChange={setAddr(setForm, "zip")} /></Field>
            <Field label="P.O. Box No."><Input value={form.residential_address?.po_box || ""} onChange={setAddr(setForm, "po_box")} /></Field>
          </div>
        </>
      )}

      {isUAEResident && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="UAE Visa No."><Input value={form.uae_visa_number || ""} onChange={set(setForm, "uae_visa_number")} /></Field>
          <Field label="UAE Visa Expiry"><Input type="date" value={form.uae_visa_expiry || ""} onChange={set(setForm, "uae_visa_expiry")} /></Field>
        </div>
      )}

      <label className="flex items-center gap-1.5 text-xs text-gray-600 py-1">
        <input type="checkbox" checked={!!form.is_pep} onChange={setBool(setForm, "is_pep")} />
        Politically Exposed Person (PEP)
      </label>

      <div className="flex justify-end gap-3 mt-3">
        <button onClick={onCancel} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={onSave} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
      </div>
    </div>
  );
}
