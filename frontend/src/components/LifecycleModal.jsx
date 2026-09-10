import React, { useEffect, useState } from "react";
import { lifecycleApi } from "../api/endpoints";
import { Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "./ui";
import DocumentsPanel from "./DocumentsPanel";
import {
  CLOSURE_METHOD_OPTIONS, RESTORATION_STATUS_OPTIONS, STRIKE_OFF_CAUSE_OPTIONS,
  LIFECYCLE_CHECKLIST_STATUS_OPTIONS, RESTORATION_CHECKLIST_ITEMS, REGISTERED_AGENT_OPTIONS,
} from "../utils/constants";

const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

const fallbackChecklist = () =>
  RESTORATION_CHECKLIST_ITEMS.map((i) => ({ ...i, status: "Pending", note: null }));

export default function LifecycleModal({ caseItem, onClose }) {
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    lifecycleApi.get(caseItem.id)
      .then((d) => { if (alive) { setForm({ ...d, restoration_checklist: d.restoration_checklist?.length ? d.restoration_checklist : fallbackChecklist() }); setError(null); } })
      .catch((e) => { if (alive) setError(e.response?.data?.detail || "Failed to load lifecycle record"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [caseItem.id]);

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
  const setBool = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));
  const setChecklist = (idx, field) => (e) => setForm((p) => {
    const next = p.restoration_checklist.map((row, i) =>
      i === idx ? { ...row, [field]: e.target.value } : row);
    return { ...p, restoration_checklist: next };
  });

  const save = async () => {
    setSaving(true);
    try {
      const { id, case_id, created_at, updated_at, ...patch } = form;
      const updated = await lifecycleApi.update(caseItem.id, cleanPayload(patch));
      onClose(true, updated);
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  return (
    <Modal title={`Entity Lifecycle — ${caseItem.company_name}`} onClose={() => onClose(false)}>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} /> : form && (
        <div className="space-y-4">
          <p className="text-[11px] text-gray-400">
            The case status ({caseItem.status}) is set automatically from the fields below —
            initiating closure, recording a strike-off date, or completing a restoration each move it.
          </p>

          <Section title="Closure / Strike-off / Lapse">
            <div className="grid grid-cols-2 gap-x-3">
              <Field label="Closure Method">
                <Select value={form.closure_method || ""} onChange={set("closure_method")}>
                  <option value="">— select —</option>
                  {CLOSURE_METHOD_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Closure Initiated Date"><Input type="date" value={form.closure_initiated_date || ""} onChange={set("closure_initiated_date")} /></Field>
            </div>
            <Field label="Closure Reason"><Textarea value={form.closure_reason || ""} onChange={set("closure_reason")} /></Field>
            <div className="grid grid-cols-2 gap-x-3 items-end">
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-2">
                <input type="checkbox" checked={!!form.client_acknowledgement_received} onChange={setBool("client_acknowledgement_received")} />
                Written client acknowledgement received (§X)
              </label>
              <Field label="Acknowledgement Date"><Input type="date" value={form.client_acknowledgement_date || ""} onChange={set("client_acknowledgement_date")} /></Field>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-2">
                <input type="checkbox" checked={!!form.outstanding_filings_cleared} onChange={setBool("outstanding_filings_cleared")} />
                Outstanding filings cleared
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-2">
                <input type="checkbox" checked={!!form.strike_off_in_good_standing} onChange={setBool("strike_off_in_good_standing")} />
                Struck off in good standing
              </label>
              <Field label="Strike-off Date"><Input type="date" value={form.strike_off_date || ""} onChange={set("strike_off_date")} /></Field>
              <Field label="Expected Dissolution Date (strike-off + 7 yrs)"><Input type="date" value={form.expected_dissolution_date || ""} onChange={set("expected_dissolution_date")} /></Field>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-2">
                <input type="checkbox" checked={!!form.dissolution_confirmed} onChange={setBool("dissolution_confirmed")} />
                Dissolution confirmed by Registry
              </label>
              <Field label="Dissolution Date"><Input type="date" value={form.dissolution_date || ""} onChange={set("dissolution_date")} /></Field>
            </div>
          </Section>

          <Section title="Restoration (§XI)">
            <div className="grid grid-cols-3 gap-x-3">
              <Field label="Restoration Status">
                <Select value={form.restoration_status || "Not Applicable"} onChange={set("restoration_status")}>
                  {RESTORATION_STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Initiated Date"><Input type="date" value={form.restoration_initiated_date || ""} onChange={set("restoration_initiated_date")} /></Field>
              <Field label="Completed Date"><Input type="date" value={form.restoration_completed_date || ""} onChange={set("restoration_completed_date")} /></Field>
              <Field label="Strike-off Cause">
                <Select value={form.strike_off_cause || ""} onChange={set("strike_off_cause")}>
                  <option value="">— select —</option>
                  {STRIKE_OFF_CAUSE_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
            </div>

            <p className="text-xs font-semibold text-gray-500 mt-2 mb-1">Restoration document checklist</p>
            <div className="space-y-1">
              {(form.restoration_checklist || []).map((row, idx) => (
                <div key={row.key} className="grid grid-cols-[1fr_110px_1fr] gap-2 items-center">
                  <span className="text-xs text-gray-700">{row.label}</span>
                  <select value={row.status || "Pending"} onChange={setChecklist(idx, "status")}
                    className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-blue-400">
                    {LIFECYCLE_CHECKLIST_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
                  </select>
                  <input value={row.note || ""} onChange={setChecklist(idx, "note")} placeholder="Note"
                    className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-blue-400" />
                </div>
              ))}
            </div>

            <p className="text-xs font-semibold text-gray-500 mt-3 mb-1">Restoration evidence files</p>
            <DocumentsPanel caseId={caseItem.id} scope={null} defaultCategory="Restoration" />
          </Section>

          <Section title="Registered-Agent Transfer">
            <div className="grid grid-cols-2 gap-x-3">
              <Field label="From Agent">
                <Select value={form.transfer_from_agent || ""} onChange={set("transfer_from_agent")}>
                  <option value="">— select —</option>
                  {REGISTERED_AGENT_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="To Agent">
                <Select value={form.transfer_to_agent || ""} onChange={set("transfer_to_agent")}>
                  <option value="">— select —</option>
                  {REGISTERED_AGENT_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Initiated Date"><Input type="date" value={form.transfer_initiated_date || ""} onChange={set("transfer_initiated_date")} /></Field>
              <Field label="Completed Date"><Input type="date" value={form.transfer_completed_date || ""} onChange={set("transfer_completed_date")} /></Field>
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-700 mt-1">
              <input type="checkbox" checked={!!form.transfer_ends_administration} onChange={setBool("transfer_ends_administration")} />
              This transfer ends Triam's administration (case becomes "Transferred Out")
            </label>
            <Field label="Transfer Notes"><Textarea value={form.transfer_notes || ""} onChange={set("transfer_notes")} /></Field>
          </Section>

          <div className="flex justify-end gap-3 pt-1">
            <button onClick={() => onClose(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} disabled={saving} className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-60" style={{ background: "#2B6D9A" }}>
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

const Section = ({ title, children }) => (
  <div>
    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">{title}</p>
    {children}
  </div>
);
