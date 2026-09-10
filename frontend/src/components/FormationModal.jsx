import React, { useEffect, useMemo, useState } from "react";
import { formationApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "./ui";
import {
  SCREENING_STATUS_OPTIONS, MLRO_SIGNOFF_STATUS_OPTIONS, VISTRA_STATUS_OPTIONS,
  SCREENING_TOOL_OPTIONS,
} from "../utils/constants";

const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

const MILESTONES = [
  ["kyc_pack_sent_date", "KYC pack sent to Vistra"],
  ["data_input_sheet_sent_date", "Data Input Sheet sent"],
  ["incorporation_submitted_date", "Incorporation submitted"],
  ["rod_filed_date", "Register of Directors filed (21-day rule)"],
  ["registers_completed_date", "Registers completed (VIRRGIN)"],
  ["formation_completed_date", "Formation completed"],
];

export default function FormationModal({ caseItem, users = [], onClose }) {
  const role = useAuthStore((s) => s.user?.role);
  const canSignOff = role === "admin" || role === "screening";
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const usersById = useMemo(() => Object.fromEntries((users || []).map((u) => [u.id, u])), [users]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    formationApi.get(caseItem.id)
      .then((d) => { if (alive) { setForm(d); setError(null); } })
      .catch((e) => { if (alive) setError(e.response?.data?.detail || "Failed to load formation record"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [caseItem.id]);

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
  const setBool = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));

  const save = async () => {
    setSaving(true);
    try {
      const {
        id, case_id, created_at, updated_at,
        screened_by_id, mlro_signoff_by_id, mlro_signoff_at, ...patch
      } = form;
      const updated = await formationApi.update(caseItem.id, cleanPayload(patch));
      onClose(true, updated);
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const nameOf = (uid) => usersById[uid]?.name || (uid ? `User #${uid}` : "—");

  return (
    <Modal title={`Formation — ${caseItem.company_name}`} onClose={() => onClose(false)}>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} /> : form && (
        <div className="space-y-4">
          <Section title="Name / World-Check Screening">
            <div className="grid grid-cols-3 gap-x-3">
              <Field label="Screening Status">
                <Select value={form.screening_status || "Not Started"} onChange={set("screening_status")}>
                  {SCREENING_STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Screening Date"><Input type="date" value={form.screening_date || ""} onChange={set("screening_date")} /></Field>
              <Field label="Tool">
                <Select value={form.screening_tool || ""} onChange={set("screening_tool")}>
                  <option value="">— select —</option>
                  {SCREENING_TOOL_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="World-Check / Reference"><Input value={form.world_check_reference || ""} onChange={set("world_check_reference")} /></Field>
            <div className="flex flex-wrap gap-4 py-1">
              <label className="flex items-center gap-2 text-xs text-gray-700">
                <input type="checkbox" checked={!!form.sanctions_hit} onChange={setBool("sanctions_hit")} /> Sanctions hit
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-700">
                <input type="checkbox" checked={!!form.pep_hit} onChange={setBool("pep_hit")} /> PEP hit
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-700">
                <input type="checkbox" checked={!!form.adverse_media_hit} onChange={setBool("adverse_media_hit")} /> Adverse media
              </label>
            </div>
            <Field label="Findings"><Textarea value={form.screening_findings || ""} onChange={set("screening_findings")} /></Field>
            <p className="text-[11px] text-gray-400">Screened by {nameOf(form.screened_by_id)}</p>
          </Section>

          <Section title="MLRO Sign-off">
            <div className="grid grid-cols-2 gap-x-3">
              <Field label="MLRO Sign-off Status">
                <Select value={form.mlro_signoff_status || "Pending"} disabled={!canSignOff} onChange={set("mlro_signoff_status")}>
                  {MLRO_SIGNOFF_STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="MLRO Notes"><Textarea value={form.mlro_signoff_notes || ""} onChange={set("mlro_signoff_notes")} /></Field>
            {form.mlro_signoff_at && (
              <p className="text-[11px] text-gray-400">
                {form.mlro_signoff_status} by {nameOf(form.mlro_signoff_by_id)} on {(form.mlro_signoff_at || "").slice(0, 10)}
              </p>
            )}
            {!canSignOff && <p className="text-[11px] text-gray-400">Only the MLRO (Screening / Admin) can change the sign-off status.</p>}
          </Section>

          <Section title="Vistra Compliance Review">
            <div className="grid grid-cols-3 gap-x-3">
              <Field label="Vistra Status">
                <Select value={form.vistra_status || "Not Submitted"} onChange={set("vistra_status")}>
                  {VISTRA_STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Submitted Date"><Input type="date" value={form.vistra_submitted_date || ""} onChange={set("vistra_submitted_date")} /></Field>
              <Field label="Approved Date"><Input type="date" value={form.vistra_approved_date || ""} onChange={set("vistra_approved_date")} /></Field>
              <Field label="Vistra Officer"><Input value={form.vistra_officer || ""} onChange={set("vistra_officer")} /></Field>
              <Field label="Query Raised Date"><Input type="date" value={form.vistra_query_raised_date || ""} onChange={set("vistra_query_raised_date")} /></Field>
              <Field label="Query Resolved Date"><Input type="date" value={form.vistra_query_resolved_date || ""} onChange={set("vistra_query_resolved_date")} /></Field>
            </div>
            <Field label="Vistra Query"><Textarea value={form.vistra_query_text || ""} onChange={set("vistra_query_text")} /></Field>
          </Section>

          <Section title="Formation Milestones (§V)">
            <div className="grid grid-cols-2 gap-x-3">
              {MILESTONES.map(([k, label]) => (
                <Field key={k} label={label}><Input type="date" value={form[k] || ""} onChange={set(k)} /></Field>
              ))}
            </div>
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
