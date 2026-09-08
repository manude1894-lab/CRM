import React, { useEffect, useState } from "react";
import { companyProfileApi } from "../api/endpoints";
import { Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "./ui";
import {
  REGISTERED_AGENT_OPTIONS, NAME_CHECK_STATUS_OPTIONS, SOURCE_OF_FUNDS_OPTIONS,
  NATURE_OF_BUSINESS_OPTIONS, COMPANY_SECRETARY_OPTIONS,
} from "../utils/constants";

const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

const ACTIVATION_DOCS = [
  ["act_certificate_of_incorporation", "Certificate of Incorporation"],
  ["act_memorandum_articles", "Memorandum & Articles of Association"],
  ["act_register_of_members", "Register of Members"],
  ["act_register_of_directors_stamped", "Register of Directors (stamped)"],
  ["act_company_stamp", "Company Stamp"],
];

export default function CompanyDetailsModal({ caseItem, onClose }) {
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    companyProfileApi.get(caseItem.id)
      .then((p) => { if (alive) { setForm(p); setError(null); } })
      .catch((e) => { if (alive) setError(e.response?.data?.detail || "Failed to load company profile"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [caseItem.id]);

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
  const setBool = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.checked }));

  const save = async () => {
    setSaving(true);
    try {
      const { id, case_id, created_at, updated_at, ...patch } = form;
      await companyProfileApi.update(caseItem.id, cleanPayload(patch));
      onClose(true);
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  return (
    <Modal title={`Company Details — ${caseItem.company_name}`} onClose={() => onClose(false)}>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} /> : form && (
        <div className="space-y-4">
          <Section title="Formation">
            <div className="grid grid-cols-3 gap-x-3">
              <Field label="Proposed Name 1"><Input value={form.proposed_name_1 || ""} onChange={set("proposed_name_1")} /></Field>
              <Field label="Proposed Name 2"><Input value={form.proposed_name_2 || ""} onChange={set("proposed_name_2")} /></Field>
              <Field label="Proposed Name 3"><Input value={form.proposed_name_3 || ""} onChange={set("proposed_name_3")} /></Field>
              <Field label="Name Check Status">
                <Select value={form.name_check_status || "Not Submitted"} onChange={set("name_check_status")}>
                  {NAME_CHECK_STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Name Confirmed Date"><Input type="date" value={form.name_confirmed_date || ""} onChange={set("name_confirmed_date")} /></Field>
              <Field label="Registered Agent">
                <Select value={form.registered_agent || ""} onChange={set("registered_agent")}>
                  <option value="">— select —</option>
                  {REGISTERED_AGENT_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Incorporation Date"><Input type="date" value={form.incorporation_date || ""} onChange={set("incorporation_date")} /></Field>
              <Field label="Company Number"><Input value={form.company_number || ""} onChange={set("company_number")} /></Field>
              <Field label="Chinese Name"><Input value={form.chinese_name || ""} onChange={set("chinese_name")} /></Field>
            </div>
          </Section>

          <Section title="Share Capital">
            <div className="grid grid-cols-4 gap-x-3 items-end">
              <Field label="Authorised Shares"><Input type="number" min="0" value={form.authorised_shares ?? ""} onChange={set("authorised_shares")} placeholder="50000" /></Field>
              <Field label="Par Value"><Input type="number" min="0" step="0.0001" value={form.par_value ?? ""} onChange={set("par_value")} placeholder="1.00" /></Field>
              <Field label="Currency"><Input value={form.share_currency || ""} onChange={set("share_currency")} placeholder="USD" /></Field>
              <label className="flex items-center gap-1.5 text-xs text-gray-600 mb-4">
                <input type="checkbox" checked={!!form.no_par_value} onChange={setBool("no_par_value")} /> No par value
              </label>
            </div>
          </Section>

          <Section title="Business">
            <div className="grid grid-cols-2 gap-x-3">
              <Field label="Source of Funds">
                <Select value={form.source_of_funds || ""} onChange={set("source_of_funds")}>
                  <option value="">— select —</option>
                  {SOURCE_OF_FUNDS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
              <Field label="Nature of Business">
                <Select value={form.nature_of_business || ""} onChange={set("nature_of_business")}>
                  <option value="">— select —</option>
                  {NATURE_OF_BUSINESS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="Source of Funds — Description"><Textarea value={form.source_of_funds_description || ""} onChange={set("source_of_funds_description")} /></Field>
            <Field label="Business Description"><Textarea value={form.business_description || ""} onChange={set("business_description")} /></Field>
            <Field label="Company Secretary">
              <Select value={form.company_secretary || ""} onChange={set("company_secretary")}>
                <option value="">— select —</option>
                {COMPANY_SECRETARY_OPTIONS.map((o) => <option key={o}>{o}</option>)}
              </Select>
            </Field>
          </Section>

          <Section title="Financial Year-Ends">
            <div className="grid grid-cols-2 gap-x-3">
              <Field label="Economic Substance FY-end (MM-DD)"><Input value={form.es_financial_year_end || ""} onChange={set("es_financial_year_end")} placeholder="12-31" /></Field>
              <Field label="Accounting FY-end (MM-DD)"><Input value={form.accounting_financial_year_end || ""} onChange={set("accounting_financial_year_end")} placeholder="12-31" /></Field>
            </div>
          </Section>

          <Section title="Activation Documents Received">
            <div className="space-y-1.5">
              {ACTIVATION_DOCS.map(([k, label]) => (
                <label key={k} className="flex items-center gap-2 text-xs text-gray-700">
                  <input type="checkbox" checked={!!form[k]} onChange={setBool(k)} /> {label}
                </label>
              ))}
            </div>
            <Field label="Activation Docs Received Date"><Input type="date" value={form.activation_docs_received_date || ""} onChange={set("activation_docs_received_date")} /></Field>
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
