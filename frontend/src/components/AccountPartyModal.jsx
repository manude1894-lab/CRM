import React, { useEffect, useState } from "react";
import { accountPartiesApi, countriesApi } from "../api/endpoints";
import { Icon, Modal, Field, Input, Select, CountrySelect, Spinner, ErrorBanner, DateInput, PassportNote } from "./ui";
import { COUNTRY_CALLING_CODES, fmtDate, isUAE } from "../utils/constants";
import { toast } from "../store/toast";
import { useAuthStore } from "../store/auth";
import { confirmDialog, reasonDialog } from "../store/confirm";
import { dialCodeForCountry, dialCodeOptions } from "../utils/dialCodes";
import MobileNumberInput from "./MobileNumberInput";
import { mobileProblem } from "../utils/mobile";
import ClientDocumentsFolder from "./accounts/ClientDocumentsFolder";
import { FOUNDATION_ROLES, isFoundation } from "./accounts/accountForm";

const CORPORATE_ROLES = ["Shareholder", "Director", "Authorised Signatory"];
const INDIVIDUAL_ROLES = ["Joint Holder"];  // BRD: individual clients have joint holders

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
  nationality: "",
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

export const partyLabel = (role) => role;

// The details that belong to the person, not to their role on this client.
const PERSON_FIELDS = ["constitution", "full_name", "dob_or_incorp_date", "id_or_license_expiry", "country_of_incorp_or_birth",
  "mobile_country_code", "mobile_number", "email", "nationality", "country_of_residence", "residential_address",
  "uae_visa_number", "uae_visa_expiry", "is_pep"];
const pick = (row, fields) => Object.fromEntries(fields.map((f) => [f, row[f]]));

// Triam UAT 04-11-2026: one person can hold several roles. Recognised by name and date of birth.
export const samePerson = (a, b) => a.id !== b.id && (a.full_name || "").trim().toLowerCase() === (b.full_name || "").trim().toLowerCase()
  && (a.dob_or_incorp_date || null) === (b.dob_or_incorp_date || null);

// onChange runs after a party is added, changed or removed (e.g. to refresh the missing-fields list).
// role shows that one kind of party only, without tabs (the onboarding form has a section per kind, BRD §5.1–5.3).
export default function AccountPartyModal({ account, onClose, onChange, role }) {
  const readOnly = useAuthStore((s) => s.isReadOnly());
  const ROLES = role ? [role] : account.account_type === "Individual" ? INDIVIDUAL_ROLES
    : isFoundation(account) ? [...FOUNDATION_ROLES, "Authorised Signatory"] : CORPORATE_ROLES;
  const [tab, setTab] = useState(ROLES[0]);
  const [parties, setParties] = useState([]);
  const [removed, setRemoved] = useState([]);
  const [showRemoved, setShowRemoved] = useState(false);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | "new" | row id
  const [form, setForm] = useState(null);
  const [docsFor, setDocsFor] = useState(null); // party whose documents are open (Triam UAT 26-10-2026)

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [ps, cs, rm] = await Promise.all([
        accountPartiesApi.list(account.id),
        countriesApi.list().catch(() => []),
        accountPartiesApi.removed(account.id).catch(() => []),
      ]);
      setParties(ps || []);
      setRemoved(rm || []);
      setCountries(cs || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load parties");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [account.id]);

  const startNew = (constitution = "Individual") => {
    setForm({ ...emptyParty(tab), constitution }); setEditing("new");
    // Another section may have added someone since this one opened: they should be offered for copying.
    accountPartiesApi.list(account.id).then((ps) => setParties(ps || [])).catch(() => {});
  };
  const startEdit = (row) => { setForm({ ...row, residential_address: { ...BLANK_ADDRESS, ...(row.residential_address || {}) } }); setEditing(row.id); };
  const cancelForm = () => { setEditing(null); setForm(null); };

  const save = async () => {
    if (!form.full_name?.trim()) return toast.error("Full Name is required");
    // Triam UAT 09/12-11-2026: every person or entity needs Address Line 1 and City (the server asks for
    // them at Submit), so they are checked on every save, not only once a Country of Residence is chosen.
    const addr = form.residential_address || {};
    if (!(addr.line1?.trim() && addr.city?.trim()))
      return toast.error(`${form.constitution === "Entity" ? "Registered" : "Residential"} Address: Address Line 1 and City are required`);
    const mobileError = mobileProblem(form.mobile_country_code, form.mobile_number);
    if (mobileError) return toast.error(mobileError);
    try {
      const payload = cleanPayload(form);
      if (editing === "new") await accountPartiesApi.create(account.id, payload);
      else await accountPartiesApi.update(editing, payload, account.id);
      // The same person's other records: offer to keep them in step, so details are entered only once.
      const before = parties.find((p) => p.id === editing);
      const others = before ? parties.filter((p) => samePerson(p, before)) : [];
      const changed = before && JSON.stringify(pick(before, PERSON_FIELDS)) !== JSON.stringify(pick(payload, PERSON_FIELDS));
      if (others.length && changed && await confirmDialog({ title: "Same person in other roles", confirmLabel: "Update them too",
        message: `${before.full_name} is also recorded as ${others.map((o) => o.party_role).join(", ")}. Apply these details there too?` })) {
        const details = cleanPayload(pick(form, PERSON_FIELDS));
        await Promise.all(others.map((o) => accountPartiesApi.update(o.id, details, account.id)));
      }
      cancelForm();
      load();
      onChange?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  // Parties are never deleted: a removed party is kept on record with the reason (and, on an approved
  // client, the removal goes to Compliance with the amendment).
  const remove = async (row) => {
    const reason = await reasonDialog({ title: `Remove ${row.full_name}`, confirmLabel: "Remove",
      message: "The person stays on record as removed, with your reason. Their documents keep their name." });
    if (!reason) return;
    try { await accountPartiesApi.remove(row.id, account.id, reason); load(); onChange?.(); }
    catch (e) { toast.error(e.response?.data?.detail || "Remove failed"); }
  };

  const switchTab = (t) => { setTab(t); cancelForm(); };

  const rowsForTab = parties.filter((p) => p.party_role === tab);
  const removedShown = role ? removed.filter((r) => r.party_role === role) : removed;
  // Triam UAT 06-11-2026: only individuals count towards 100%; an entity's share is looked through.
  const ownershipTotal = parties
    .filter((p) => p.party_role === "Shareholder" && p.constitution !== "Entity")
    .reduce((s, p) => s + Number(p.effective_ownership_percent || 0), 0);

  return (
    <Modal title={`Parties: ${account.company_name}`} onClose={onClose}>
      {!role && (
        <div className="flex border-b border-gray-100 mb-4 -mt-2">
          {/* People already recorded stay visible, e.g. shareholders on a client that later became a foundation. */}
          {[...ROLES, ...new Set(parties.map((p) => p.party_role).filter((r) => !ROLES.includes(r)))].map((r) => (
            <button key={r} onClick={() => switchTab(r)}
              className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${tab === r ? "border-brand-500 text-brand-600" : "border-transparent text-gray-400 hover:text-gray-600"}`}>
              {partyLabel(r)} ({parties.filter((p) => p.party_role === r).length})
            </button>
          ))}
        </div>
      )}

      {tab === "Shareholder" && !editing && (
        <p className={`text-xs mb-2 ${ownershipTotal === 100 ? "text-gray-400" : "text-amber-600 font-medium"}`}>
          Total individual ownership: {ownershipTotal.toFixed(2)}%{ownershipTotal !== 100 && " (should total 100%)"} · entity shareholders are not counted
        </p>
      )}

      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <>
          {!editing && (
            <>
              <div className="space-y-2 mb-3">
                {rowsForTab.length === 0
                  ? <p className="text-sm text-gray-400 text-center py-6">No {partyLabel(tab).toLowerCase().replace(/y$/, "ie")}s on record.</p>
                  : rowsForTab.map((p, i) => (
                    <div key={p.id} className="bg-gray-50 rounded-lg">
                    <div className="flex items-center justify-between p-2.5">
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          <span className="text-xs text-gray-400 mr-1.5">{partyLabel(tab)} {i + 1}</span>
                          {p.full_name}
                          {p.is_pep && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">PEP</span>}
                          {p.nominee_director_name && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">Nominee: {p.nominee_director_name}</span>}
                        </div>
                        <div className="text-xs text-gray-400">
                          {p.constitution}
                          {parties.filter((o) => samePerson(o, p)).map((o) => (
                            <span key={o.id} className="ml-1 px-1 rounded bg-brand-50 text-brand-700">also {o.party_role}</span>
                          ))}
                          {p.country_of_incorp_or_birth && ` · ${p.country_of_incorp_or_birth}`}
                          {p.party_role === "Shareholder" && p.constitution !== "Entity" && p.effective_ownership_percent != null && ` · ${p.effective_ownership_percent}% ownership`}
                          {p.country_of_residence && ` · resides ${p.country_of_residence}`}
                        </div>
                      </div>
                      <div className="flex gap-1 items-center">
                        <button onClick={() => setDocsFor(docsFor === p.id ? null : p.id)}
                          className={`px-2 py-1 text-[11px] rounded border ${docsFor === p.id ? "border-brand-300 text-brand-700 bg-white" : "border-gray-200 text-gray-600 hover:bg-white"}`}>
                          Documents
                        </button>
                        {!readOnly && <button onClick={() => startEdit(p)} title="Edit" className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600"><Icon name="edit" size={14} /></button>}
                        {!readOnly && <button onClick={() => remove(p)} title="Remove" className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="close" size={14} /></button>}
                      </div>
                    </div>
                    {docsFor === p.id && (
                      <div className="px-2.5 pb-2.5 pt-1 border-t border-gray-100">
                        <ClientDocumentsFolder accountId={account.id} partyId={p.id} onChange={() => onChange?.()} />
                      </div>
                    )}
                    </div>
                  ))}
              </div>
              {/* Triam UAT 26-10-2026: once shareholding is 100%, no further shareholder can be added. */}
              {readOnly ? null : tab === "Shareholder" && ownershipTotal >= 100 ? (
                <div className="px-3 py-2 text-xs rounded-lg bg-gray-50 border border-gray-200 text-gray-600 text-center">
                  Individual shareholding is 100%. No further individual can be added; reduce an existing share first.
                  <button onClick={() => startNew("Entity")} className="block mx-auto mt-1 text-brand-600 hover:underline">Add an entity shareholder</button>
                </div>
              ) : (
                <button onClick={() => startNew()} className="w-full px-3 py-2 text-xs border border-dashed border-gray-300 rounded-lg hover:border-brand-300 hover:text-brand-600 text-gray-500 flex items-center justify-center gap-1">
                  <Icon name="plus" size={13} /> Add {partyLabel(tab)}
                </button>
              )}
              {removedShown.length > 0 && (
                <div className="mt-3">
                  <button onClick={() => setShowRemoved((v) => !v)} className="text-xs text-gray-500 hover:text-brand-600">
                    {showRemoved ? "Hide" : "Show"} removed ({removedShown.length})
                  </button>
                  {showRemoved && (
                    <div className="mt-2 space-y-1.5">
                      {removedShown.map((r) => (
                        <div key={r.id} className="p-2 rounded-lg border border-gray-100 text-xs text-gray-500">
                          <span className="line-through text-gray-600">{r.full_name}</span> · {r.party_role}
                          <div className="text-[11px] text-gray-400">
                            Removed {fmtDate(r.removed_at)}{r.removed_by_name ? ` by ${r.removed_by_name}` : ""}{r.removed_reason ? `. Reason: ${r.removed_reason}` : ""}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {editing && (
            <PartyForm form={form} setForm={setForm} countries={countries} onCancel={cancelForm} onSave={save}
              copyFrom={editing === "new" ? parties.filter((p, i, all) => all.findIndex((o) => o.id === p.id || samePerson(o, p)) === i) : []} />
          )}
        </>
      )}
    </Modal>
  );
}

const set = (setForm, k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
const setBool = (setForm, k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));
const setAddr = (setForm, k) => (e) => setForm((p) => ({ ...p, residential_address: { ...p.residential_address, [k]: e.target.value } }));

function PartyForm({ form, setForm, countries, onCancel, onSave, copyFrom = [] }) {
  const isShareholder = form.party_role === "Shareholder";
  const isDirector = form.party_role === "Director";
  // BRD §5.3 / §6: signatories and joint holders need mobile and email too.
  // Keep in step with CONTACT_REQUIRED / needs_country_of_birth in account_party_service.py (Triam UAT 10-11-2026).
  const contactRequired = ["Shareholder", "Director", "Authorised Signatory", "Joint Holder", ...FOUNDATION_ROLES].includes(form.party_role);
  const isEntity = form.constitution === "Entity";
  const birthRequired = form.party_role === "Authorised Signatory" || (["Shareholder", "Director"].includes(form.party_role) && !isEntity);
  const isUAEResident = isUAE(form.country_of_residence);

  // Triam UAT 04-11-2026: a director who is also a UBO needs their details entered only once.
  const copy = (e) => {
    const source = copyFrom.find((p) => p.id === Number(e.target.value));
    if (source) setForm((p) => ({ ...p, ...pick(source, PERSON_FIELDS), residential_address: { ...BLANK_ADDRESS, ...(source.residential_address || {}) } }));
  };

  return (
    <div>
      {copyFrom.length > 0 && (
        <Field label="Same person as (fetch their details)">
          <Select defaultValue="" onChange={copy}>
            <option value="">— new person —</option>
            {copyFrom.map((p) => <option key={p.id} value={p.id}>{p.full_name} ({p.party_role})</option>)}
          </Select>
        </Field>
      )}
      {!["Authorised Signatory", "Joint Holder"].includes(form.party_role) && (
        <Field label="Constitution">
          <Select value={form.constitution} onChange={set(setForm, "constitution")}>
            <option>Individual</option>
            <option>Entity</option>
          </Select>
        </Field>
      )}
      <Field label={isEntity ? "Entity Name (as per license)" : form.party_role === "Authorised Signatory" ? "Full Name (as per Resolution)"
        : form.party_role === "Joint Holder" ? "Full Name (as per passport)" : "Full Name (as per ID document)"} required>
        <Input value={form.full_name || ""} onChange={set(setForm, "full_name")} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={isEntity ? "Incorporation Date" : "Date of Birth"}>
          <DateInput value={form.dob_or_incorp_date || ""} onChange={set(setForm, "dob_or_incorp_date")} />
        </Field>
        <Field label={isEntity ? "License / CI Expiry" : "Passport Expiry"}>
          <DateInput value={form.id_or_license_expiry || ""} onChange={set(setForm, "id_or_license_expiry")} />
          {!isEntity && <PassportNote value={form.id_or_license_expiry} />}
        </Field>
      </div>
      <Field label={isEntity ? "Country of Incorporation" : "Country of Birth"} required={birthRequired}>
        <CountrySelect value={form.country_of_incorp_or_birth} onChange={set(setForm, "country_of_incorp_or_birth")} countries={countries} />
      </Field>

      {isDirector && (
        <Field label="Nominee Director's Name (if applicable)">
          <Input value={form.nominee_director_name || ""} onChange={set(setForm, "nominee_director_name")} />
        </Field>
      )}
      {isShareholder && isEntity && (
        <p className="text-xs text-gray-500 mb-3">No percentage for an entity. Add the individuals behind it with their effective share; they make up the 100%.</p>
      )}
      {isShareholder && !isEntity && (
        <Field label="Effective Ownership Share (%)" required>
          <Input type="number" min="0" max="100" step="0.01" value={form.effective_ownership_percent ?? ""} onChange={set(setForm, "effective_ownership_percent")} />
        </Field>
      )}

      <Field label="Contact Mobile" required={contactRequired}>
        <MobileNumberInput code={form.mobile_country_code} number={form.mobile_number} options={dialCodeOptions(countries, COUNTRY_CALLING_CODES)}
          onCode={(v) => setForm((p) => ({ ...p, mobile_country_code: v }))} onNumber={(v) => setForm((p) => ({ ...p, mobile_number: v }))} />
      </Field>
      <Field label="Contact Email" required={contactRequired}><Input type="email" value={form.email || ""} onChange={set(setForm, "email")} /></Field>

      <Field label="Nationality" required={!isEntity}>
        <CountrySelect value={form.nationality} onChange={set(setForm, "nationality")} countries={countries} />
      </Field>
      <Field label="Country of Residence" required>
        <CountrySelect value={form.country_of_residence} countries={countries} onChange={(e) => {
          // Triam UAT 05-11-2026: choosing the country fills the Contact Mobile code; it can still be changed.
          const code = dialCodeForCountry(e.target.value, countries);
          setForm((p) => ({ ...p, country_of_residence: e.target.value, ...(code ? { mobile_country_code: code } : {}) }));
        }} />
      </Field>

      {/* Always shown: Line 1 and City are needed for every person or entity (Triam UAT 12-11-2026). */}
      {(
        <>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1">{isEntity ? "Registered Address" : "Residential Address"}</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Address Line 1" required><Input value={form.residential_address?.line1 || ""} onChange={setAddr(setForm, "line1")} /></Field>
            <Field label="Address Line 2"><Input value={form.residential_address?.line2 || ""} onChange={setAddr(setForm, "line2")} /></Field>
            <Field label="Landmark"><Input value={form.residential_address?.landmark || ""} onChange={setAddr(setForm, "landmark")} /></Field>
            <Field label="City" required><Input value={form.residential_address?.city || ""} onChange={setAddr(setForm, "city")} /></Field>
            <Field label="ZIP Code"><Input value={form.residential_address?.zip || ""} onChange={setAddr(setForm, "zip")} /></Field>
            <Field label="P.O. Box No."><Input value={form.residential_address?.po_box || ""} onChange={setAddr(setForm, "po_box")} /></Field>
          </div>
        </>
      )}

      {isUAEResident && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="UAE Visa No."><Input value={form.uae_visa_number || ""} onChange={set(setForm, "uae_visa_number")} /></Field>
          <Field label="UAE Visa Expiry"><DateInput value={form.uae_visa_expiry || ""} onChange={set(setForm, "uae_visa_expiry")} /></Field>
        </div>
      )}

      {/* BRD §5.3 has no PEP field for authorised signatories. */}
      {form.party_role !== "Authorised Signatory" && (
        <label className="flex items-center gap-1.5 text-xs text-gray-600 py-1">
          <input type="checkbox" checked={!!form.is_pep} onChange={setBool(setForm, "is_pep")} />
          Politically Exposed Person (PEP)
        </label>
      )}

      <div className="flex justify-end gap-3 mt-3">
        <button onClick={onCancel} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={onSave} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save {form.party_role}</button>
      </div>
    </div>
  );
}
