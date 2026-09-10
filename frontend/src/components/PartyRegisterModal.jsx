import React, { useEffect, useState } from "react";
import { directorsApi, shareholdersApi, ubosApi, amlApi } from "../api/endpoints";
import { Icon, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "./ui";
import {
  PARTY_TYPE_OPTIONS, SHAREHOLDER_TYPE_OPTIONS, OWNERSHIP_NATURE_OPTIONS, SOURCE_OF_WEALTH_OPTIONS,
  ENTITY_DETAIL_TYPE_OPTIONS, CHARGE_STATUS_OPTIONS,
} from "../utils/constants";

const emptyAppendixA = {
  email: "", mobile: "", occupation: "", employer_name: "",
  tax_residency_country: "", tax_id_number: "", source_of_funds: "", source_of_wealth: "",
  is_pep: false, pep_notes: "",
};

const emptyDirector = {
  director_type: "Individual",
  first_name: "", middle_name: "", last_name: "", former_name: "",
  date_of_birth: "", place_of_birth: "", nationality: "", passport_number: "",
  corporate_name: "", corporate_number: "", country_of_incorporation: "", corporate_date_of_incorporation: "",
  entity_details: {},
  service_address: "", service_city: "", service_country: "",
  residential_address: "", residential_city: "", residential_country: "",
  appointment_date: "", cessation_date: "", notes: "",
  ...emptyAppendixA,
};

const emptyShareholder = {
  identification_type: "Individual",
  name: "", corporate_number: "", country_of_incorporation: "",
  entity_details: {},
  registered_address: "", city: "", country: "",
  certificate_no: "", number_of_shares: "", share_class: "", shareholding_percent: "",
  is_joint_shareholder: false, is_nominee: false, nominee_holds_for: "",
  nominator_name: "", nominator_address: "", nominator_relationship: "", nominee_agreement_date: "",
  charges: [],
  date_entered: "", date_ceased: "", notes: "",
  ...emptyAppendixA,
};

const emptyUBO = {
  first_name: "", middle_name: "", last_name: "", former_name: "",
  date_of_birth: "", place_of_birth: "", nationality: "", country_of_residence: "",
  passport_number: "", passport_expiry: "", national_id: "",
  residential_address: "", residential_city: "", residential_country: "", email: "", mobile: "",
  percentage_interest: "", ownership_nature: "Direct", nature_of_control: "", held_via_shareholder_id: "",
  is_pep: false, pep_notes: "",
  employer_name: "", job_title: "", sector: "", years_employed: "",
  source_of_wealth_category: "", source_of_wealth_details: "",
  appointment_date: "", cessation_date: "", notes: "",
};

const directorName = (d) => d.director_type === "Corporate"
  ? (d.corporate_name || "—")
  : [d.first_name, d.middle_name, d.last_name].filter(Boolean).join(" ") || "—";

const uboName = (u) => [u.first_name, u.middle_name, u.last_name].filter(Boolean).join(" ") || "—";

// Strip blank-string fields to null so optional date/number columns don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

export default function PartyRegisterModal({ caseItem, onClose }) {
  const [tab, setTab] = useState("directors");
  const [directors, setDirectors] = useState([]);
  const [shareholders, setShareholders] = useState([]);
  const [ubos, setUbos] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | "new" | row id
  const [form, setForm] = useState(null);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [ds, ss, us, cs] = await Promise.all([
        directorsApi.list(caseItem.id),
        shareholdersApi.list(caseItem.id),
        ubosApi.list(caseItem.id),
        amlApi.countryRisk().catch(() => []),
      ]);
      setDirectors(ds || []);
      setShareholders(ss || []);
      setUbos(us || []);
      setCountries(cs || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load register");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [caseItem.id]);

  const emptyFor = (t) => t === "directors" ? { ...emptyDirector } : t === "shareholders" ? { ...emptyShareholder } : { ...emptyUBO };
  const startNew = () => { setForm(emptyFor(tab)); setEditing("new"); };
  const startEdit = (row) => { setForm({ ...row }); setEditing(row.id); };
  const cancelForm = () => { setEditing(null); setForm(null); };

  const api = { directors: directorsApi, shareholders: shareholdersApi, ubos: ubosApi }[tab];

  const save = async () => {
    try {
      const payload = cleanPayload(form);
      if (editing === "new") await api.create(caseItem.id, payload);
      else await api.update(editing, payload);
      cancelForm();
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (row) => {
    const label = tab === "directors" ? directorName(row) : tab === "ubos" ? uboName(row) : row.name;
    if (!confirm(`Remove ${label}?`)) return;
    try { await api.delete(row.id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  const switchTab = (t) => { setTab(t); cancelForm(); };

  const TABS = [
    ["directors", `Directors (${directors.length})`],
    ["shareholders", `Shareholders (${shareholders.length})`],
    ["ubos", `UBOs (${ubos.length})`],
  ];

  return (
    <Modal title={`Registers — ${caseItem.company_name}`} onClose={onClose}>
      <div className="flex border-b border-gray-100 mb-4 -mt-2">
        {TABS.map(([t, label]) => (
          <button key={t} onClick={() => switchTab(t)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${tab === t ? "border-blue-500 text-blue-600" : "border-transparent text-gray-400 hover:text-gray-600"}`}>
            {label}
          </button>
        ))}
      </div>

      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <>
          {!editing && (
            <>
              <div className="space-y-2 mb-3">
                {tab === "directors" && (directors.length === 0
                  ? <p className="text-sm text-gray-400 text-center py-6">No directors on record.</p>
                  : directors.map((d) => (
                    <div key={d.id} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-gray-800">{directorName(d)}</div>
                        <div className="text-xs text-gray-400">
                          {d.director_type}
                          {d.director_type === "Individual" && d.nationality && ` · ${d.nationality}`}
                          {d.director_type === "Corporate" && d.country_of_incorporation && ` · ${d.country_of_incorporation}`}
                          {d.appointment_date && ` · Appointed ${d.appointment_date}`}
                          {d.cessation_date && ` · Ceased ${d.cessation_date}`}
                        </div>
                      </div>
                      <RowActions onEdit={() => startEdit(d)} onDelete={() => remove(d)} />
                    </div>
                  )))}

                {tab === "shareholders" && (shareholders.length === 0
                  ? <p className="text-sm text-gray-400 text-center py-6">No shareholders on record.</p>
                  : shareholders.map((s) => (
                    <div key={s.id} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          {s.name}
                          {s.is_nominee && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">Nominee</span>}
                          {Number(s.shareholding_percent) >= 10 && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">10%+ CDD</span>}
                        </div>
                        <div className="text-xs text-gray-400">
                          {s.identification_type}
                          {s.number_of_shares != null && ` · ${s.number_of_shares} shares`}
                          {s.shareholding_percent != null && ` · ${s.shareholding_percent}%`}
                          {s.share_class && ` · ${s.share_class}`}
                        </div>
                      </div>
                      <RowActions onEdit={() => startEdit(s)} onDelete={() => remove(s)} />
                    </div>
                  )))}

                {tab === "ubos" && (ubos.length === 0
                  ? <p className="text-sm text-gray-400 text-center py-6">No ultimate beneficial owners on record.</p>
                  : ubos.map((u) => (
                    <div key={u.id} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
                      <div>
                        <div className="text-sm font-medium text-gray-800">
                          {uboName(u)}
                          {u.is_pep && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">PEP</span>}
                          {Number(u.percentage_interest) >= 10 && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-700">10%+ CDD</span>}
                        </div>
                        <div className="text-xs text-gray-400">
                          {u.percentage_interest != null && `${u.percentage_interest}% · `}{u.ownership_nature}
                          {u.nationality && ` · ${u.nationality}`}
                          {u.source_of_wealth_category && ` · SoW: ${u.source_of_wealth_category}`}
                          {u.cessation_date && ` · Ceased ${u.cessation_date}`}
                        </div>
                      </div>
                      <RowActions onEdit={() => startEdit(u)} onDelete={() => remove(u)} />
                    </div>
                  )))}
              </div>
              <button onClick={startNew} className="w-full px-3 py-2 text-xs border border-dashed border-gray-300 rounded-lg hover:border-blue-300 hover:text-blue-600 text-gray-500 flex items-center justify-center gap-1">
                <Icon name="plus" size={13} /> Add {tab === "directors" ? "Director" : tab === "shareholders" ? "Shareholder" : "UBO"}
              </button>
            </>
          )}

          {editing && tab === "directors" && (
            <DirectorForm form={form} setForm={setForm} onCancel={cancelForm} onSave={save} />
          )}
          {editing && tab === "shareholders" && (
            <ShareholderForm form={form} setForm={setForm} onCancel={cancelForm} onSave={save} />
          )}
          {editing && tab === "ubos" && (
            <UBOForm form={form} setForm={setForm} onCancel={cancelForm} onSave={save}
              countries={countries} shareholders={shareholders} />
          )}
        </>
      )}
    </Modal>
  );
}

const RowActions = ({ onEdit, onDelete }) => (
  <div className="flex gap-1">
    <button onClick={onEdit} className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600"><Icon name="edit" size={14} /></button>
    <button onClick={onDelete} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={14} /></button>
  </div>
);

const FormButtons = ({ onCancel, onSave }) => (
  <div className="flex justify-end gap-3 mt-2">
    <button onClick={onCancel} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
    <button onClick={onSave} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
  </div>
);

const set = (setForm, k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
const setBool = (setForm, k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));

const SectionTitle = ({ children }) => (
  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1">{children}</p>
);

// ─── Vistra KYC Appendix A — individual detail (Director + individual Shareholder) ──
function AppendixAFields({ form, setForm }) {
  return (
    <>
      <SectionTitle>Appendix A — Individual Detail</SectionTitle>
      <div className="grid grid-cols-3 gap-x-3">
        <Field label="Email"><Input value={form.email || ""} onChange={set(setForm, "email")} /></Field>
        <Field label="Mobile"><Input value={form.mobile || ""} onChange={set(setForm, "mobile")} /></Field>
        <Field label="Occupation"><Input value={form.occupation || ""} onChange={set(setForm, "occupation")} /></Field>
        <Field label="Employer"><Input value={form.employer_name || ""} onChange={set(setForm, "employer_name")} /></Field>
        <Field label="Tax Residency (country)"><Input value={form.tax_residency_country || ""} onChange={set(setForm, "tax_residency_country")} /></Field>
        <Field label="Tax ID Number"><Input value={form.tax_id_number || ""} onChange={set(setForm, "tax_id_number")} /></Field>
      </div>
      <Field label="Source of Funds"><Input value={form.source_of_funds || ""} onChange={set(setForm, "source_of_funds")} /></Field>
      <Field label="Source of Wealth"><Textarea value={form.source_of_wealth || ""} onChange={set(setForm, "source_of_wealth")} /></Field>
      <label className="flex items-center gap-1.5 text-xs text-gray-600 py-1">
        <input type="checkbox" checked={!!form.is_pep} onChange={setBool(setForm, "is_pep")} />
        Politically Exposed Person (PEP)
      </label>
      {form.is_pep && <Field label="PEP Notes"><Textarea value={form.pep_notes || ""} onChange={set(setForm, "pep_notes")} /></Field>}
    </>
  );
}

// ─── Small editor for a list of strings (beneficiaries, council members, LPs) ──
function StringListEditor({ label, value = [], onChange }) {
  const list = Array.isArray(value) ? value : [];
  const upd = (i, v) => onChange(list.map((x, idx) => (idx === i ? v : x)));
  return (
    <Field label={label}>
      <div className="space-y-1">
        {list.map((v, i) => (
          <div key={i} className="flex gap-1">
            <Input value={v} onChange={(e) => upd(i, e.target.value)} />
            <button type="button" onClick={() => onChange(list.filter((_, idx) => idx !== i))}
              className="px-2 text-xs text-gray-400 hover:text-red-500">✕</button>
          </div>
        ))}
        <button type="button" onClick={() => onChange([...list, ""])}
          className="text-xs px-2 py-0.5 border border-gray-200 rounded hover:bg-gray-50">＋ Add</button>
      </div>
    </Field>
  );
}

// ─── Vistra KYC Appendix B — entity-variant detail (stored in entity_details JSON) ──
const ENTITY_FIELDS = {
  Company: [["regulated", "Regulated? (yes/no)"], ["regulator", "Regulator"], ["listed", "Listed? (yes/no)"], ["exchange", "Exchange"], ["directors_summary", "Directors — summary"], ["ownership_summary", "Ownership — summary"]],
  Trust: [["trust_name", "Trust name"], ["trust_type", "Trust type"], ["trustee", "Trustee"], ["settlor", "Settlor"], ["protector", "Protector"], ["governing_law", "Governing law"], ["date_established", "Date established"]],
  Foundation: [["foundation_name", "Foundation name"], ["founder", "Founder"], ["guardian", "Guardian"], ["governing_law", "Governing law"], ["date_established", "Date established"]],
  Fund: [["fund_name", "Fund name"], ["fund_manager", "Fund manager"], ["investment_advisor", "Investment advisor"], ["administrator", "Administrator"], ["regulated", "Regulated? (yes/no)"], ["regulator", "Regulator"], ["domicile", "Domicile"]],
  "Limited Partnership": [["general_partner", "General partner"], ["partnership_agreement_date", "Partnership agreement date"]],
  "State-Owned Enterprise": [["government_body", "Government body"], ["country", "Country"], ["government_ownership_percent", "Government ownership %"], ["legal_form", "Legal form"]],
};

function EntityDetailsFields({ value = {}, onChange }) {
  const d = value || {};
  const type = d.entity_type || "";
  const upd = (k, v) => onChange({ ...d, [k]: v });
  const lists = { Trust: "beneficiaries", Foundation: "council_members", "Limited Partnership": "limited_partners" };
  return (
    <>
      <SectionTitle>Appendix B — Entity Detail</SectionTitle>
      <Field label="Entity Type">
        <Select value={type} onChange={(e) => onChange({ ...d, entity_type: e.target.value })}>
          <option value="">— select —</option>
          {ENTITY_DETAIL_TYPE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
        </Select>
      </Field>
      {type && (
        <>
          <div className="grid grid-cols-2 gap-x-3">
            {(ENTITY_FIELDS[type] || []).map(([k, label]) => (
              <Field key={k} label={label}><Input value={d[k] ?? ""} onChange={(e) => upd(k, e.target.value)} /></Field>
            ))}
          </div>
          {lists[type] && (
            <StringListEditor label={lists[type].replace("_", " ")} value={d[lists[type]]} onChange={(v) => upd(lists[type], v)} />
          )}
          {(type === "Trust" || type === "Foundation") && (
            <StringListEditor label="Beneficiaries" value={d.beneficiaries} onChange={(v) => upd("beneficiaries", v)} />
          )}
        </>
      )}
    </>
  );
}

// ─── Mortgages & charges over a share position ──
const emptyCharge = { chargee: "", amount: "", currency: "USD", date_created: "", date_satisfied: "", status: "Outstanding" };

function ChargesEditor({ value = [], onChange }) {
  const list = Array.isArray(value) ? value : [];
  const upd = (i, k, v) => onChange(list.map((c, idx) => (idx === i ? { ...c, [k]: v } : c)));
  return (
    <>
      <SectionTitle>Mortgages & Charges</SectionTitle>
      {list.length === 0 && <p className="text-xs text-gray-400 italic">No charges recorded.</p>}
      <div className="space-y-2">
        {list.map((c, i) => (
          <div key={i} className="border border-gray-100 rounded-lg p-2 grid grid-cols-3 gap-x-2 gap-y-1 relative">
            <Field label="Chargee"><Input value={c.chargee || ""} onChange={(e) => upd(i, "chargee", e.target.value)} /></Field>
            <Field label="Amount"><Input type="number" min="0" value={c.amount ?? ""} onChange={(e) => upd(i, "amount", e.target.value)} /></Field>
            <Field label="Currency"><Input value={c.currency || ""} onChange={(e) => upd(i, "currency", e.target.value)} /></Field>
            <Field label="Date Created"><Input type="date" value={c.date_created || ""} onChange={(e) => upd(i, "date_created", e.target.value)} /></Field>
            <Field label="Date Satisfied"><Input type="date" value={c.date_satisfied || ""} onChange={(e) => upd(i, "date_satisfied", e.target.value)} /></Field>
            <Field label="Status">
              <Select value={c.status || "Outstanding"} onChange={(e) => upd(i, "status", e.target.value)}>
                {CHARGE_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <button type="button" onClick={() => onChange(list.filter((_, idx) => idx !== i))}
              className="absolute top-1 right-1 text-xs text-gray-300 hover:text-red-500">✕</button>
          </div>
        ))}
      </div>
      <button type="button" onClick={() => onChange([...list, { ...emptyCharge }])}
        className="text-xs px-2 py-0.5 mt-1 border border-gray-200 rounded hover:bg-gray-50">＋ Add charge</button>
    </>
  );
}

function DirectorForm({ form, setForm, onCancel, onSave }) {
  return (
    <div className="space-y-1">
      <Field label="Director Type">
        <Select value={form.director_type} onChange={set(setForm, "director_type")}>
          {PARTY_TYPE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
        </Select>
      </Field>
      {form.director_type === "Individual" ? (
        <div className="grid grid-cols-3 gap-x-3">
          <Field label="First Name"><Input value={form.first_name || ""} onChange={set(setForm, "first_name")} /></Field>
          <Field label="Middle Name"><Input value={form.middle_name || ""} onChange={set(setForm, "middle_name")} /></Field>
          <Field label="Last Name"><Input value={form.last_name || ""} onChange={set(setForm, "last_name")} /></Field>
          <Field label="Date of Birth"><Input type="date" value={form.date_of_birth || ""} onChange={set(setForm, "date_of_birth")} /></Field>
          <Field label="Place of Birth"><Input value={form.place_of_birth || ""} onChange={set(setForm, "place_of_birth")} /></Field>
          <Field label="Nationality"><Input value={form.nationality || ""} onChange={set(setForm, "nationality")} /></Field>
          <Field label="Passport Number"><Input value={form.passport_number || ""} onChange={set(setForm, "passport_number")} /></Field>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-x-3">
          <Field label="Corporate Name"><Input value={form.corporate_name || ""} onChange={set(setForm, "corporate_name")} /></Field>
          <Field label="Corporate Number"><Input value={form.corporate_number || ""} onChange={set(setForm, "corporate_number")} /></Field>
          <Field label="Country of Incorporation"><Input value={form.country_of_incorporation || ""} onChange={set(setForm, "country_of_incorporation")} /></Field>
          <Field label="Date of Incorporation"><Input type="date" value={form.corporate_date_of_incorporation || ""} onChange={set(setForm, "corporate_date_of_incorporation")} /></Field>
        </div>
      )}
      {form.director_type === "Individual"
        ? <AppendixAFields form={form} setForm={setForm} />
        : <EntityDetailsFields value={form.entity_details} onChange={(v) => setForm((p) => ({ ...p, entity_details: v }))} />}
      <SectionTitle>Address & Appointment</SectionTitle>
      <div className="grid grid-cols-3 gap-x-3">
        <Field label="Service Address"><Input value={form.service_address || ""} onChange={set(setForm, "service_address")} /></Field>
        <Field label="Service City"><Input value={form.service_city || ""} onChange={set(setForm, "service_city")} /></Field>
        <Field label="Service Country"><Input value={form.service_country || ""} onChange={set(setForm, "service_country")} /></Field>
        <Field label="Residential/Registered Address"><Input value={form.residential_address || ""} onChange={set(setForm, "residential_address")} /></Field>
        <Field label="Residential/Registered City"><Input value={form.residential_city || ""} onChange={set(setForm, "residential_city")} /></Field>
        <Field label="Residential/Registered Country"><Input value={form.residential_country || ""} onChange={set(setForm, "residential_country")} /></Field>
        <Field label="Appointment Date"><Input type="date" value={form.appointment_date || ""} onChange={set(setForm, "appointment_date")} /></Field>
        <Field label="Cessation Date"><Input type="date" value={form.cessation_date || ""} onChange={set(setForm, "cessation_date")} /></Field>
      </div>
      <FormButtons onCancel={onCancel} onSave={onSave} />
    </div>
  );
}

function ShareholderForm({ form, setForm, onCancel, onSave }) {
  return (
    <div className="space-y-1">
      <div className="grid grid-cols-2 gap-x-3">
        <Field label="Identification Type">
          <Select value={form.identification_type} onChange={set(setForm, "identification_type")}>
            {SHAREHOLDER_TYPE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
          </Select>
        </Field>
        <Field label="Name" required><Input value={form.name || ""} onChange={set(setForm, "name")} /></Field>
        {form.identification_type !== "Individual" && (
          <>
            <Field label="Corporate Number"><Input value={form.corporate_number || ""} onChange={set(setForm, "corporate_number")} /></Field>
            <Field label="Country of Incorporation"><Input value={form.country_of_incorporation || ""} onChange={set(setForm, "country_of_incorporation")} /></Field>
          </>
        )}
        <Field label="Registered Address"><Input value={form.registered_address || ""} onChange={set(setForm, "registered_address")} /></Field>
        <Field label="City"><Input value={form.city || ""} onChange={set(setForm, "city")} /></Field>
        <Field label="Country"><Input value={form.country || ""} onChange={set(setForm, "country")} /></Field>
        <Field label="Certificate No."><Input value={form.certificate_no || ""} onChange={set(setForm, "certificate_no")} /></Field>
        <Field label="Number of Shares"><Input type="number" min="0" value={form.number_of_shares ?? ""} onChange={set(setForm, "number_of_shares")} /></Field>
        <Field label="Share Class"><Input value={form.share_class || ""} onChange={set(setForm, "share_class")} /></Field>
        <Field label="Shareholding %"><Input type="number" min="0" max="100" step="0.01" value={form.shareholding_percent ?? ""} onChange={set(setForm, "shareholding_percent")} /></Field>
        <Field label="Date Entered"><Input type="date" value={form.date_entered || ""} onChange={set(setForm, "date_entered")} /></Field>
        <Field label="Date Ceased"><Input type="date" value={form.date_ceased || ""} onChange={set(setForm, "date_ceased")} /></Field>
      </div>
      <div className="flex items-center gap-4 py-1">
        <label className="flex items-center gap-1.5 text-xs text-gray-600">
          <input type="checkbox" checked={!!form.is_joint_shareholder} onChange={setBool(setForm, "is_joint_shareholder")} />
          Joint shareholder
        </label>
        <label className="flex items-center gap-1.5 text-xs text-gray-600">
          <input type="checkbox" checked={!!form.is_nominee} onChange={setBool(setForm, "is_nominee")} />
          Nominee shareholder
        </label>
      </div>
      {form.is_nominee && (
        <>
          <Field label="Nominee Holds For (beneficial owner)"><Input value={form.nominee_holds_for || ""} onChange={set(setForm, "nominee_holds_for")} /></Field>
          <div className="grid grid-cols-2 gap-x-3">
            <Field label="Nominator Name"><Input value={form.nominator_name || ""} onChange={set(setForm, "nominator_name")} /></Field>
            <Field label="Nominator Address"><Input value={form.nominator_address || ""} onChange={set(setForm, "nominator_address")} /></Field>
            <Field label="Relationship"><Input value={form.nominator_relationship || ""} onChange={set(setForm, "nominator_relationship")} /></Field>
            <Field label="Nominee Agreement Date"><Input type="date" value={form.nominee_agreement_date || ""} onChange={set(setForm, "nominee_agreement_date")} /></Field>
          </div>
        </>
      )}

      {form.identification_type === "Individual"
        ? <AppendixAFields form={form} setForm={setForm} />
        : <EntityDetailsFields value={form.entity_details} onChange={(v) => setForm((p) => ({ ...p, entity_details: v }))} />}

      <ChargesEditor value={form.charges} onChange={(v) => setForm((p) => ({ ...p, charges: v }))} />

      <Field label="Notes"><Textarea value={form.notes || ""} onChange={set(setForm, "notes")} /></Field>
      <FormButtons onCancel={onCancel} onSave={onSave} />
    </div>
  );
}

function UBOForm({ form, setForm, onCancel, onSave, countries, shareholders }) {
  const CountrySelect = ({ k }) => (
    <Select value={form[k] || ""} onChange={set(setForm, k)}>
      <option value="">— select —</option>
      {countries.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
    </Select>
  );
  return (
    <div className="space-y-1">
      <div className="grid grid-cols-3 gap-x-3">
        <Field label="First Name"><Input value={form.first_name || ""} onChange={set(setForm, "first_name")} /></Field>
        <Field label="Middle Name"><Input value={form.middle_name || ""} onChange={set(setForm, "middle_name")} /></Field>
        <Field label="Last Name"><Input value={form.last_name || ""} onChange={set(setForm, "last_name")} /></Field>
        <Field label="Date of Birth"><Input type="date" value={form.date_of_birth || ""} onChange={set(setForm, "date_of_birth")} /></Field>
        <Field label="Place of Birth"><Input value={form.place_of_birth || ""} onChange={set(setForm, "place_of_birth")} /></Field>
        <Field label="Nationality"><CountrySelect k="nationality" /></Field>
        <Field label="Country of Residence"><CountrySelect k="country_of_residence" /></Field>
        <Field label="Passport Number"><Input value={form.passport_number || ""} onChange={set(setForm, "passport_number")} /></Field>
        <Field label="Passport Expiry"><Input type="date" value={form.passport_expiry || ""} onChange={set(setForm, "passport_expiry")} /></Field>
      </div>
      <div className="grid grid-cols-3 gap-x-3">
        <Field label="Residential Address"><Input value={form.residential_address || ""} onChange={set(setForm, "residential_address")} /></Field>
        <Field label="City"><Input value={form.residential_city || ""} onChange={set(setForm, "residential_city")} /></Field>
        <Field label="Country"><Input value={form.residential_country || ""} onChange={set(setForm, "residential_country")} /></Field>
        <Field label="Email"><Input value={form.email || ""} onChange={set(setForm, "email")} /></Field>
        <Field label="Mobile"><Input value={form.mobile || ""} onChange={set(setForm, "mobile")} /></Field>
      </div>
      <div className="grid grid-cols-3 gap-x-3">
        <Field label="Interest %"><Input type="number" min="0" max="100" step="0.01" value={form.percentage_interest ?? ""} onChange={set(setForm, "percentage_interest")} /></Field>
        <Field label="Ownership Nature">
          <Select value={form.ownership_nature} onChange={set(setForm, "ownership_nature")}>
            {OWNERSHIP_NATURE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
          </Select>
        </Field>
        <Field label="Nature of Control"><Input value={form.nature_of_control || ""} onChange={set(setForm, "nature_of_control")} placeholder="e.g. voting rights" /></Field>
        <Field label="Held Via (shareholder)">
          <Select value={form.held_via_shareholder_id || ""} onChange={set(setForm, "held_via_shareholder_id")}>
            <option value="">— Direct / none —</option>
            {shareholders.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </Field>
        <Field label="Appointment Date"><Input type="date" value={form.appointment_date || ""} onChange={set(setForm, "appointment_date")} /></Field>
        <Field label="Cessation Date"><Input type="date" value={form.cessation_date || ""} onChange={set(setForm, "cessation_date")} /></Field>
      </div>
      <label className="flex items-center gap-1.5 text-xs text-gray-600 py-1">
        <input type="checkbox" checked={!!form.is_pep} onChange={setBool(setForm, "is_pep")} />
        Politically Exposed Person (PEP)
      </label>
      {form.is_pep && <Field label="PEP Notes"><Textarea value={form.pep_notes || ""} onChange={set(setForm, "pep_notes")} /></Field>}
      <div className="grid grid-cols-4 gap-x-3">
        <Field label="Employer"><Input value={form.employer_name || ""} onChange={set(setForm, "employer_name")} /></Field>
        <Field label="Job Title"><Input value={form.job_title || ""} onChange={set(setForm, "job_title")} /></Field>
        <Field label="Sector"><Input value={form.sector || ""} onChange={set(setForm, "sector")} /></Field>
        <Field label="Years Employed"><Input value={form.years_employed || ""} onChange={set(setForm, "years_employed")} placeholder="e.g. 3+ years" /></Field>
      </div>
      <Field label="Source of Wealth — Category">
        <Select value={form.source_of_wealth_category || ""} onChange={set(setForm, "source_of_wealth_category")}>
          <option value="">— select —</option>
          {SOURCE_OF_WEALTH_OPTIONS.map((o) => <option key={o}>{o}</option>)}
        </Select>
      </Field>
      <Field label="Source of Wealth — Details"><Textarea value={form.source_of_wealth_details || ""} onChange={set(setForm, "source_of_wealth_details")} /></Field>
      <Field label="Notes"><Textarea value={form.notes || ""} onChange={set(setForm, "notes")} /></Field>
      <FormButtons onCancel={onCancel} onSave={onSave} />
    </div>
  );
}
