import React, { useEffect, useState } from "react";
import { activitiesApi, instructionsApi } from "../../api/endpoints";
import { Modal, Field, Input, Select, Textarea, Spinner, DateInput } from "../ui";
import { toast } from "../../store/toast";
import { useMasters } from "../../hooks/useMasters";
import { selectableCodes } from "../../hooks/masterUtils";
import { INSTRUCTION_TYPE_OPTIONS, fmtDate } from "../../utils/constants";
import ActivityForm, { activityPayload, activityProblem, blankActivity } from "../activities/ActivityForm";
import ActivityCard from "../activities/ActivityCard";

const STATUS_STYLE = { Pending: "bg-amber-50 text-amber-700", "In Progress": "bg-blue-50 text-blue-700", Completed: "bg-emerald-50 text-emerald-700", "On Hold": "bg-gray-100 text-gray-600" };

/**
 * BRD §17 — servicing an existing client: its Visit / Call Reports and activity history, and its
 * Service Requests, in one place on the client.
 */
export default function ClientServicingModal({ account, cases = [], onClose, startWith = null }) {
  const [tab, setTab] = useState(startWith === "request" ? "requests" : "reports");
  const [activities, setActivities] = useState(null);
  const [requests, setRequests] = useState(null);
  const [form, setForm] = useState(null); // activity form, when open
  // service request form, when open (Triam mark-up §11: opened straight from the client, with its details)
  const [sr, setSr] = useState(startWith === "request"
    ? { instruction_type: "", case_id: "", date_received: new Date().toISOString().split("T")[0], charge_amount: "", comments: "" } : null);
  const [busy, setBusy] = useState(false);
  const requestTypes = useMasters("service_request_type", INSTRUCTION_TYPE_OPTIONS);
  const clientCases = cases.filter((c) => c.account_id === account.id);

  const load = () => {
    activitiesApi.list({ account_id: account.id, limit: 200 }).then((r) => setActivities(r.items || [])).catch(() => setActivities([]));
    instructionsApi.list({ account_id: account.id, limit: 200 }).then((r) => setRequests(r.items || [])).catch(() => setRequests([]));
  };
  useEffect(load, [account.id]);

  const saveActivity = async () => {
    const problem = activityProblem(form);
    if (problem) return toast.error(problem);
    setBusy(true);
    try {
      const payload = activityPayload(form);
      if (form.id) await activitiesApi.update(form.id, payload); else await activitiesApi.create(payload);
      toast.success(`${form.activity_type} saved`);
      setForm(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); } finally { setBusy(false); }
  };

  const saveRequest = async () => {
    if (!sr.instruction_type) return toast.error("Choose the request type");
    setBusy(true);
    try {
      await instructionsApi.create({
        account_id: account.id, case_id: sr.case_id ? Number(sr.case_id) : null, instruction_type: sr.instruction_type,
        status: "Pending", date_received: sr.date_received || null, comments: sr.comments || null,
        charge_amount: sr.charge_amount === "" ? null : sr.charge_amount,
      });
      toast.success("Service request created");
      setSr(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); } finally { setBusy(false); }
  };

  const tabBtn = (key, label, count) => (
    <button onClick={() => setTab(key)}
      className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${tab === key ? "border-brand-500 text-brand-600" : "border-transparent text-gray-400 hover:text-gray-600"}`}>
      {label}{count != null && ` (${count})`}
    </button>
  );

  return (
    <Modal title={`Servicing — ${account.company_name}`} onClose={onClose}>
      <div className="text-xs text-gray-500 -mt-2 mb-2">Client ID <span className="font-mono font-semibold text-gray-700">{account.client_id || "—"}</span></div>
      <div className="flex border-b border-gray-100 mb-3">
        {tabBtn("reports", "Visit & Call Reports", activities?.length)}
        {tabBtn("requests", "Service Requests", requests?.length)}
      </div>

      {tab === "reports" && (form ? (
        <div>
          <ActivityForm form={form} setForm={setForm} cases={clientCases} lockClient />
          <div className="flex justify-end gap-2">
            <button onClick={() => setForm(null)} className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={saveActivity} disabled={busy} className="px-3 py-1.5 text-sm text-white rounded-lg disabled:opacity-60" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2">
            <button onClick={() => setForm(blankActivity(account.id, "Visit Report"))} className="px-2.5 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>+ Visit Report</button>
            <button onClick={() => setForm(blankActivity(account.id, "Call Report"))} className="px-2.5 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>+ Call Report</button>
            <button onClick={() => setForm(blankActivity(account.id, "Meeting"))} className="px-2.5 py-1 text-xs border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50">+ Other activity</button>
          </div>
          {activities === null ? <Spinner /> : activities.length === 0
            ? <p className="text-sm text-gray-400 text-center py-6">No activities recorded for this client yet.</p>
            : activities.map((a) => (
              <ActivityCard key={a.id} activity={a} compact
                onEdit={() => setForm({ ...blankActivity(account.id), ...a, account_id: a.account_id || account.id, case_id: a.case_id || "" })} />
            ))}
        </div>
      ))}

      {tab === "requests" && (sr ? (
        <div>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Request Type" required>
              <Select value={sr.instruction_type} onChange={(e) => setSr((p) => ({ ...p, instruction_type: e.target.value }))}>
                <option value="">— choose —</option>
                {selectableCodes(requestTypes.items, sr.instruction_type).map((t) => <option key={t} value={t}>{requestTypes.labelOf(t)}</option>)}
              </Select>
            </Field>
            <Field label="Case / entity (optional)">
              <Select value={sr.case_id} onChange={(e) => setSr((p) => ({ ...p, case_id: e.target.value }))}>
                <option value="">— none —</option>
                {clientCases.map((c) => <option key={c.id} value={c.id}>{c.case_uid} – {c.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Date Received"><DateInput value={sr.date_received} onChange={(e) => setSr((p) => ({ ...p, date_received: e.target.value }))} /></Field>
            <Field label="Charge (to client)"><Input type="number" min="0" step="0.01" value={sr.charge_amount} onChange={(e) => setSr((p) => ({ ...p, charge_amount: e.target.value }))} /></Field>
          </div>
          <Field label="Details"><Textarea rows={3} value={sr.comments} onChange={(e) => setSr((p) => ({ ...p, comments: e.target.value }))} /></Field>
          <div className="flex justify-end gap-2">
            <button onClick={() => setSr(null)} className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={saveRequest} disabled={busy} className="px-3 py-1.5 text-sm text-white rounded-lg disabled:opacity-60" style={{ background: "#1a3a5c" }}>Create</button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <button onClick={() => setSr({ instruction_type: "", case_id: "", date_received: new Date().toISOString().split("T")[0], charge_amount: "", comments: "" })}
            className="px-2.5 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>+ New Service Request</button>
          {requests === null ? <Spinner /> : requests.length === 0
            ? <p className="text-sm text-gray-400 text-center py-6">No service requests for this client yet.</p>
            : (
              <table className="w-full text-xs">
                <thead><tr className="text-gray-500 border-b border-gray-100">
                  <th className="text-left py-1.5 font-semibold">Request</th><th className="text-left py-1.5 font-semibold">Status</th>
                  <th className="text-left py-1.5 font-semibold">Received</th><th className="text-left py-1.5 font-semibold">Completed</th>
                </tr></thead>
                <tbody>
                  {requests.map((r) => (
                    <tr key={r.id} className="border-b border-gray-50 align-top">
                      <td className="py-1.5 pr-2 text-gray-700">{r.instruction_type}{r.comments && <div className="text-gray-400">{r.comments}</div>}</td>
                      <td className="py-1.5"><span className={`px-1.5 py-0.5 rounded ${STATUS_STYLE[r.status] || "bg-gray-100"}`}>{r.status}</span></td>
                      <td className="py-1.5 text-gray-500">{fmtDate(r.date_received) || "—"}</td>
                      <td className="py-1.5 text-gray-500">{fmtDate(r.date_completed) || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      ))}
    </Modal>
  );
}
