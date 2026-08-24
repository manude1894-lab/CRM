import React, { useEffect, useState } from "react";
import { directorsApi, shareholdersApi } from "../api/endpoints";
import { Icon, Modal, Field, Input, Select, Spinner, ErrorBanner } from "./ui";
import { PARTY_TYPE_OPTIONS, SHAREHOLDER_TYPE_OPTIONS } from "../utils/constants";

const emptyDirector = {
  director_type: "Individual",
  first_name: "", middle_name: "", last_name: "", former_name: "",
  date_of_birth: "", place_of_birth: "", nationality: "", passport_number: "",
  corporate_name: "", corporate_number: "", country_of_incorporation: "", corporate_date_of_incorporation: "",
  service_address: "", service_city: "", service_country: "",
  residential_address: "", residential_city: "", residential_country: "",
  appointment_date: "", cessation_date: "", notes: "",
};

const emptyShareholder = {
  identification_type: "Individual",
  name: "", corporate_number: "", country_of_incorporation: "",
  registered_address: "", city: "", country: "",
  certificate_no: "", number_of_shares: "", share_class: "", shareholding_percent: "",
  is_joint_shareholder: false, is_nominee: false, nominee_holds_for: "",
  date_entered: "", date_ceased: "", notes: "",
};

const directorName = (d) => d.director_type === "Corporate"
  ? (d.corporate_name || "—")
  : [d.first_name, d.middle_name, d.last_name].filter(Boolean).join(" ") || "—";

// Strip blank-string fields to null so optional date/number columns don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

export default function PartyRegisterModal({ caseItem, onClose }) {
  const [tab, setTab] = useState("directors");
  const [directors, setDirectors] = useState([]);
  const [shareholders, setShareholders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(null); // null | "new" | row id
  const [form, setForm] = useState(null);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [ds, ss] = await Promise.all([
        directorsApi.list(caseItem.id),
        shareholdersApi.list(caseItem.id),
      ]);
      setDirectors(ds || []);
      setShareholders(ss || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load register");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [caseItem.id]);

  const startNew = () => {
    setForm(tab === "directors" ? { ...emptyDirector } : { ...emptyShareholder });
    setEditing("new");
  };
  const startEdit = (row) => {
    setForm({ ...row });
    setEditing(row.id);
  };
  const cancelForm = () => { setEditing(null); setForm(null); };

  const save = async () => {
    try {
      const payload = cleanPayload(form);
      if (tab === "directors") {
        if (editing === "new") await directorsApi.create(caseItem.id, payload);
        else await directorsApi.update(editing, payload);
      } else {
        if (editing === "new") await shareholdersApi.create(caseItem.id, payload);
        else await shareholdersApi.update(editing, payload);
      }
      cancelForm();
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (row) => {
    if (!confirm(`Remove ${tab === "directors" ? directorName(row) : row.name}?`)) return;
    try {
      if (tab === "directors") await directorsApi.delete(row.id);
      else await shareholdersApi.delete(row.id);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Delete failed");
    }
  };

  const switchTab = (t) => { setTab(t); cancelForm(); };

  return (
    <Modal title={`Directors & Shareholders — ${caseItem.company_name}`} onClose={onClose}>
      <div className="flex border-b border-gray-100 mb-4 -mt-2">
        {["directors", "shareholders"].map((t) => (
          <button key={t} onClick={() => switchTab(t)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${tab === t ? "border-blue-500 text-blue-600" : "border-transparent text-gray-400 hover:text-gray-600"}`}>
            {t === "directors" ? `Directors (${directors.length})` : `Shareholders (${shareholders.length})`}
          </button>
        ))}
      </div>

      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <>
          {!editing && (
            <>
              <div className="space-y-2 mb-3">
                {tab === "directors" ? (
                  directors.length === 0
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
                        <div className="flex gap-1">
                          <button onClick={() => startEdit(d)} className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600"><Icon name="edit" size={14} /></button>
                          <button onClick={() => remove(d)} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={14} /></button>
                        </div>
                      </div>
                    ))
                ) : (
                  shareholders.length === 0
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
                        <div className="flex gap-1">
                          <button onClick={() => startEdit(s)} className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600"><Icon name="edit" size={14} /></button>
                          <button onClick={() => remove(s)} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={14} /></button>
                        </div>
                      </div>
                    ))
                )}
              </div>
              <button onClick={startNew} className="w-full px-3 py-2 text-xs border border-dashed border-gray-300 rounded-lg hover:border-blue-300 hover:text-blue-600 text-gray-500 flex items-center justify-center gap-1">
                <Icon name="plus" size={13} /> Add {tab === "directors" ? "Director" : "Shareholder"}
              </button>
            </>
          )}

          {editing && tab === "directors" && (
            <div className="space-y-1">
              <Field label="Director Type">
                <Select value={form.director_type} onChange={(e) => setForm((p) => ({ ...p, director_type: e.target.value }))}>
                  {PARTY_TYPE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              {form.director_type === "Individual" ? (
                <div className="grid grid-cols-3 gap-x-3">
                  <Field label="First Name"><Input value={form.first_name || ""} onChange={(e) => setForm((p) => ({ ...p, first_name: e.target.value }))} /></Field>
                  <Field label="Middle Name"><Input value={form.middle_name || ""} onChange={(e) => setForm((p) => ({ ...p, middle_name: e.target.value }))} /></Field>
                  <Field label="Last Name"><Input value={form.last_name || ""} onChange={(e) => setForm((p) => ({ ...p, last_name: e.target.value }))} /></Field>
                  <Field label="Date of Birth"><Input type="date" value={form.date_of_birth || ""} onChange={(e) => setForm((p) => ({ ...p, date_of_birth: e.target.value }))} /></Field>
                  <Field label="Place of Birth"><Input value={form.place_of_birth || ""} onChange={(e) => setForm((p) => ({ ...p, place_of_birth: e.target.value }))} /></Field>
                  <Field label="Nationality"><Input value={form.nationality || ""} onChange={(e) => setForm((p) => ({ ...p, nationality: e.target.value }))} /></Field>
                  <Field label="Passport Number"><Input value={form.passport_number || ""} onChange={(e) => setForm((p) => ({ ...p, passport_number: e.target.value }))} /></Field>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-x-3">
                  <Field label="Corporate Name"><Input value={form.corporate_name || ""} onChange={(e) => setForm((p) => ({ ...p, corporate_name: e.target.value }))} /></Field>
                  <Field label="Corporate Number"><Input value={form.corporate_number || ""} onChange={(e) => setForm((p) => ({ ...p, corporate_number: e.target.value }))} /></Field>
                  <Field label="Country of Incorporation"><Input value={form.country_of_incorporation || ""} onChange={(e) => setForm((p) => ({ ...p, country_of_incorporation: e.target.value }))} /></Field>
                  <Field label="Date of Incorporation"><Input type="date" value={form.corporate_date_of_incorporation || ""} onChange={(e) => setForm((p) => ({ ...p, corporate_date_of_incorporation: e.target.value }))} /></Field>
                </div>
              )}
              <div className="grid grid-cols-3 gap-x-3">
                <Field label="Service Address"><Input value={form.service_address || ""} onChange={(e) => setForm((p) => ({ ...p, service_address: e.target.value }))} /></Field>
                <Field label="Service City"><Input value={form.service_city || ""} onChange={(e) => setForm((p) => ({ ...p, service_city: e.target.value }))} /></Field>
                <Field label="Service Country"><Input value={form.service_country || ""} onChange={(e) => setForm((p) => ({ ...p, service_country: e.target.value }))} /></Field>
                <Field label="Residential/Registered Address"><Input value={form.residential_address || ""} onChange={(e) => setForm((p) => ({ ...p, residential_address: e.target.value }))} /></Field>
                <Field label="Residential/Registered City"><Input value={form.residential_city || ""} onChange={(e) => setForm((p) => ({ ...p, residential_city: e.target.value }))} /></Field>
                <Field label="Residential/Registered Country"><Input value={form.residential_country || ""} onChange={(e) => setForm((p) => ({ ...p, residential_country: e.target.value }))} /></Field>
                <Field label="Appointment Date"><Input type="date" value={form.appointment_date || ""} onChange={(e) => setForm((p) => ({ ...p, appointment_date: e.target.value }))} /></Field>
                <Field label="Cessation Date"><Input type="date" value={form.cessation_date || ""} onChange={(e) => setForm((p) => ({ ...p, cessation_date: e.target.value }))} /></Field>
              </div>
              <div className="flex justify-end gap-3 mt-2">
                <button onClick={cancelForm} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
              </div>
            </div>
          )}

          {editing && tab === "shareholders" && (
            <div className="space-y-1">
              <div className="grid grid-cols-2 gap-x-3">
                <Field label="Identification Type">
                  <Select value={form.identification_type} onChange={(e) => setForm((p) => ({ ...p, identification_type: e.target.value }))}>
                    {SHAREHOLDER_TYPE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </Select>
                </Field>
                <Field label="Name" required><Input value={form.name || ""} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></Field>
                {form.identification_type !== "Individual" && (
                  <>
                    <Field label="Corporate Number"><Input value={form.corporate_number || ""} onChange={(e) => setForm((p) => ({ ...p, corporate_number: e.target.value }))} /></Field>
                    <Field label="Country of Incorporation"><Input value={form.country_of_incorporation || ""} onChange={(e) => setForm((p) => ({ ...p, country_of_incorporation: e.target.value }))} /></Field>
                  </>
                )}
                <Field label="Registered Address"><Input value={form.registered_address || ""} onChange={(e) => setForm((p) => ({ ...p, registered_address: e.target.value }))} /></Field>
                <Field label="City"><Input value={form.city || ""} onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))} /></Field>
                <Field label="Country"><Input value={form.country || ""} onChange={(e) => setForm((p) => ({ ...p, country: e.target.value }))} /></Field>
                <Field label="Certificate No."><Input value={form.certificate_no || ""} onChange={(e) => setForm((p) => ({ ...p, certificate_no: e.target.value }))} /></Field>
                <Field label="Number of Shares"><Input type="number" min="0" value={form.number_of_shares ?? ""} onChange={(e) => setForm((p) => ({ ...p, number_of_shares: e.target.value }))} /></Field>
                <Field label="Share Class"><Input value={form.share_class || ""} onChange={(e) => setForm((p) => ({ ...p, share_class: e.target.value }))} /></Field>
                <Field label="Shareholding %"><Input type="number" min="0" max="100" step="0.01" value={form.shareholding_percent ?? ""} onChange={(e) => setForm((p) => ({ ...p, shareholding_percent: e.target.value }))} /></Field>
                <Field label="Date Entered"><Input type="date" value={form.date_entered || ""} onChange={(e) => setForm((p) => ({ ...p, date_entered: e.target.value }))} /></Field>
                <Field label="Date Ceased"><Input type="date" value={form.date_ceased || ""} onChange={(e) => setForm((p) => ({ ...p, date_ceased: e.target.value }))} /></Field>
              </div>
              <div className="flex items-center gap-4 py-1">
                <label className="flex items-center gap-1.5 text-xs text-gray-600">
                  <input type="checkbox" checked={!!form.is_joint_shareholder} onChange={(e) => setForm((p) => ({ ...p, is_joint_shareholder: e.target.checked }))} />
                  Joint shareholder
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-600">
                  <input type="checkbox" checked={!!form.is_nominee} onChange={(e) => setForm((p) => ({ ...p, is_nominee: e.target.checked }))} />
                  Nominee shareholder
                </label>
              </div>
              {form.is_nominee && (
                <Field label="Nominee Holds For (beneficial owner)"><Input value={form.nominee_holds_for || ""} onChange={(e) => setForm((p) => ({ ...p, nominee_holds_for: e.target.value }))} /></Field>
              )}
              <div className="flex justify-end gap-3 mt-2">
                <button onClick={cancelForm} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
              </div>
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
