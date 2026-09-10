import React, { useEffect, useState } from "react";
import { pepApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Badge, Modal, Field, Input, Select, Textarea } from "./ui";
import { PEP_TYPE_OPTIONS, PEP_RISK_CONCLUSION_OPTIONS } from "../utils/constants";

const clean = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, v === "" ? null : v]));

const emptyForm = () => ({
  subject_name: "", pep_type: "", position: "", pep_jurisdiction: "",
  since_date: "", still_in_office: false, family_and_associates: "",
  source_of_wealth_scrutiny: "", source_of_funds_scrutiny: "", edd_measures: "",
  adverse_media_findings: "", risk_conclusion: "", senior_management_approved: false,
  assessment_date: "", notes: "", director_id: null, shareholder_id: null, ubo_id: null,
});

export default function PEPAssessmentPanel({ caseId, parties = [] }) {
  const role = useAuthStore((s) => s.user?.role);
  const canSignOff = role === "admin" || role === "screening";
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState(emptyForm());

  const load = async () => {
    setLoading(true);
    try { setItems(await pepApi.list(caseId)); }
    catch { setItems([]); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (caseId) load(); }, [caseId]);

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
  const setBool = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));

  const partyValue = form.director_id ? `d${form.director_id}` : form.shareholder_id ? `s${form.shareholder_id}` : form.ubo_id ? `u${form.ubo_id}` : "";
  const onParty = (e) => {
    const v = e.target.value;
    const kindMap = { d: "director_id", s: "shareholder_id", u: "ubo_id" };
    const next = { director_id: null, shareholder_id: null, ubo_id: null };
    if (v) {
      next[kindMap[v[0]]] = Number(v.slice(1));
      const p = parties.find((x) => `${x._kind[0].toLowerCase()}${x.id}` === v);
      if (p && !form.subject_name) next.subject_name = p._label;
    }
    setForm((prev) => ({ ...prev, ...next, ...(next.subject_name ? { subject_name: next.subject_name } : {}) }));
  };

  const openNew = () => { setForm(emptyForm()); setModal(true); };
  const openEdit = (a) => {
    setForm({
      ...emptyForm(), ...a,
      since_date: a.since_date ?? "", assessment_date: a.assessment_date ?? "",
    });
    setModal(true);
  };

  const save = async () => {
    const payload = clean({ ...form, case_id: caseId });
    delete payload.id; delete payload.created_at; delete payload.updated_at;
    delete payload.approved_by_id; delete payload.approved_at; delete payload.assessed_by_id;
    try {
      if (form.id) await pepApi.update(form.id, payload);
      else await pepApi.create(caseId, payload);
      setModal(false); load();
    } catch (e) { alert(e.response?.data?.detail || "Save failed"); }
  };

  const remove = async (a) => {
    if (!confirm(`Delete the PEP assessment for ${a.subject_name}?`)) return;
    try { await pepApi.remove(a.id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className="border-t border-gray-100 pt-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-600">PEP / EDD Assessments</p>
        <button onClick={openNew} className="text-xs px-2 py-1 border border-gray-200 rounded-lg hover:bg-gray-50">＋ Add</button>
      </div>

      {loading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No PEP assessments recorded.</p>
      ) : (
        <div className="space-y-1.5">
          {items.map((a) => (
            <div key={a.id} className="flex items-center justify-between gap-2 p-2 bg-gray-50 rounded-lg">
              <button onClick={() => openEdit(a)} className="text-xs text-left hover:text-blue-600">
                <span className="font-medium text-gray-700">{a.subject_name}</span>
                <span className="text-gray-400"> · {a.pep_type || "PEP"}</span>
              </button>
              <div className="flex items-center gap-2">
                {a.risk_conclusion && <Badge text={a.risk_conclusion} />}
                {a.senior_management_approved && <span className="text-[11px] text-emerald-600">approved</span>}
                <button onClick={() => remove(a)} className="text-gray-400 hover:text-red-500 text-xs">✕</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <Modal title={form.id ? "PEP Assessment" : "New PEP Assessment"} onClose={() => setModal(false)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Party">
              <Select value={partyValue} onChange={onParty}>
                <option value="">— Not linked —</option>
                {parties.map((p) => (
                  <option key={`${p._kind}${p.id}`} value={`${p._kind[0].toLowerCase()}${p.id}`}>{p._kind} — {p._label}</option>
                ))}
              </Select>
            </Field>
            <Field label="Subject Name" required><Input value={form.subject_name || ""} onChange={set("subject_name")} /></Field>
            <Field label="PEP Type">
              <Select value={form.pep_type || ""} onChange={set("pep_type")}>
                <option value="">— select —</option>
                {PEP_TYPE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
              </Select>
            </Field>
            <Field label="Position / Office"><Input value={form.position || ""} onChange={set("position")} /></Field>
            <Field label="Jurisdiction"><Input value={form.pep_jurisdiction || ""} onChange={set("pep_jurisdiction")} /></Field>
            <Field label="PEP Since"><Input type="date" value={form.since_date || ""} onChange={set("since_date")} /></Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-700 my-1">
            <input type="checkbox" checked={!!form.still_in_office} onChange={setBool("still_in_office")} /> Still in office
          </label>
          <Field label="Family Members & Close Associates"><Textarea value={form.family_and_associates || ""} onChange={set("family_and_associates")} /></Field>
          <Field label="Source of Wealth — Scrutiny"><Textarea value={form.source_of_wealth_scrutiny || ""} onChange={set("source_of_wealth_scrutiny")} /></Field>
          <Field label="Source of Funds — Scrutiny"><Textarea value={form.source_of_funds_scrutiny || ""} onChange={set("source_of_funds_scrutiny")} /></Field>
          <Field label="EDD Measures Applied"><Textarea value={form.edd_measures || ""} onChange={set("edd_measures")} /></Field>
          <Field label="Adverse Media Findings"><Textarea value={form.adverse_media_findings || ""} onChange={set("adverse_media_findings")} /></Field>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Risk Conclusion">
              <Select value={form.risk_conclusion || ""} disabled={!canSignOff} onChange={set("risk_conclusion")}>
                <option value="">— select —</option>
                {PEP_RISK_CONCLUSION_OPTIONS.map((o) => <option key={o}>{o}</option>)}
              </Select>
            </Field>
            <Field label="Assessment Date"><Input type="date" value={form.assessment_date || ""} onChange={set("assessment_date")} /></Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-700 my-1">
            <input type="checkbox" checked={!!form.senior_management_approved} disabled={!canSignOff} onChange={setBool("senior_management_approved")} />
            Senior-management approved
          </label>
          {!canSignOff && <p className="text-[11px] text-gray-400">Only the MLRO (Screening / Admin) can set the risk conclusion or approval.</p>}
          <Field label="Notes"><Textarea value={form.notes || ""} onChange={set("notes")} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
