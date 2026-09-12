import React, { useEffect, useState } from "react";
import { serviceSubscriptionsApi } from "../api/endpoints";
import { Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, Badge } from "./ui";
import { SERVICE_NAME_SUGGESTIONS, SERVICE_BILLING_FREQUENCY_OPTIONS, SERVICE_SUBSCRIPTION_STATUS_OPTIONS, fmtFull } from "../utils/constants";

const empty = {
  service_name: "", billing_frequency: "Monthly", fee_amount: "",
  status: "Active", start_date: "", next_billing_date: "", notes: "",
};

export default function ServiceSubscriptionsModal({ caseItem, onClose }) {
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(null); // non-null while add/edit form is open
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    serviceSubscriptionsApi.list(caseItem.id)
      .then((rows) => { setSubs(rows || []); setError(null); })
      .catch((e) => setError(e.response?.data?.detail || "Failed to load service subscriptions"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [caseItem.id]);

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form, fee_amount: form.fee_amount || null, start_date: form.start_date || null, next_billing_date: form.next_billing_date || null };
      if (form.id) {
        const { id, case_id, created_at, updated_at, ...patch } = payload;
        await serviceSubscriptionsApi.update(form.id, patch);
      } else {
        await serviceSubscriptionsApi.create(caseItem.id, payload);
      }
      setForm(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!confirm("Remove this service subscription?")) return;
    try {
      await serviceSubscriptionsApi.remove(id);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <Modal title={`Services — ${caseItem.company_name}`} onClose={() => onClose(false)}>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} /> : (
        <div className="space-y-3">
          <p className="text-xs text-gray-400">
            Recurring services subscribed by this entity. Active subscriptions auto-generate a Draft invoice
            when their next billing date arrives.
          </p>

          {subs.length === 0 && !form && <p className="text-sm text-gray-400">No services on file yet.</p>}

          {subs.map((s) => (
            <div key={s.id} className="border border-gray-100 rounded-lg p-3 flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-gray-800">{s.service_name}</div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {s.billing_frequency} · {s.fee_amount ? fmtFull(s.fee_amount) : "no fee set"}
                  {s.next_billing_date && <> · next billing {s.next_billing_date}</>}
                </div>
                {s.notes && <div className="text-xs text-gray-400 mt-1">{s.notes}</div>}
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <Badge text={s.status} />
                <button onClick={() => setForm(s)} className="text-xs px-2 py-0.5 rounded border border-gray-200 hover:border-blue-300 hover:text-blue-600 text-gray-500">Edit</button>
                <button onClick={() => remove(s.id)} className="text-xs px-2 py-0.5 rounded border border-gray-200 hover:border-red-300 hover:text-red-500 text-gray-500">Remove</button>
              </div>
            </div>
          ))}

          {form ? (
            <div className="border border-gray-200 rounded-lg p-3 space-y-2">
              <div className="grid grid-cols-2 gap-x-3">
                <Field label="Service Name">
                  <Input list="service-name-suggestions" value={form.service_name} onChange={set("service_name")} />
                  <datalist id="service-name-suggestions">
                    {SERVICE_NAME_SUGGESTIONS.map((s) => <option key={s} value={s} />)}
                  </datalist>
                </Field>
                <Field label="Billing Frequency">
                  <Select value={form.billing_frequency} onChange={set("billing_frequency")}>
                    {SERVICE_BILLING_FREQUENCY_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </Select>
                </Field>
                <Field label="Fee Amount"><Input type="number" min="0" step="0.01" value={form.fee_amount ?? ""} onChange={set("fee_amount")} /></Field>
                <Field label="Status">
                  <Select value={form.status} onChange={set("status")}>
                    {SERVICE_SUBSCRIPTION_STATUS_OPTIONS.map((o) => <option key={o}>{o}</option>)}
                  </Select>
                </Field>
                <Field label="Start Date"><Input type="date" value={form.start_date || ""} onChange={set("start_date")} /></Field>
                <Field label="Next Billing Date"><Input type="date" value={form.next_billing_date || ""} onChange={set("next_billing_date")} /></Field>
              </div>
              <Field label="Notes"><Textarea value={form.notes || ""} onChange={set("notes")} /></Field>
              <div className="flex justify-end gap-2">
                <button onClick={() => setForm(null)} className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button onClick={save} disabled={saving || !form.service_name} className="px-3 py-1.5 text-xs text-white rounded-lg disabled:opacity-60" style={{ background: "#2B6D9A" }}>
                  {saving ? "Saving…" : "Save"}
                </button>
              </div>
            </div>
          ) : (
            <button onClick={() => setForm(empty)} className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50">＋ Add Service</button>
          )}

          <div className="flex justify-end pt-1">
            <button onClick={() => onClose(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Close</button>
          </div>
        </div>
      )}
    </Modal>
  );
}
