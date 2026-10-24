import React, { useEffect, useState } from "react";
import { activitiesApi, accountsApi } from "../api/endpoints";
import { Icon, Modal, Spinner, ErrorBanner, PageHeader } from "../components/ui";
import { toast } from "../store/toast";
import { reasonDialog } from "../store/confirm";
import ActivityForm, { ACTIVITY_TYPES, activityPayload, activityProblem, blankActivity } from "../components/activities/ActivityForm";
import ActivityCard from "../components/activities/ActivityCard";

/** Visit Reports and Call Reports across all the clients this user can see (BRD §15). */
export default function ActivitiesPage() {
  const [activities, setActivities] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [typeFilter, setTypeFilter] = useState("All");
  const [clientFilter, setClientFilter] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [actRes, accRes] = await Promise.all([activitiesApi.list({ limit: 500 }), accountsApi.list({ limit: 500 })]);
      setActivities(actRes.items || []);
      setAccounts(accRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load visit and call reports");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = activities.filter((a) => (typeFilter === "All" || a.activity_type === typeFilter)
    && (!clientFilter || a.account_id === Number(clientFilter)));

  const openNew = (type) => { setForm(blankActivity(clientFilter, type)); setModal("new"); };

  const save = async () => {
    const problem = activityProblem(form);
    if (problem) return toast.error(problem);
    try {
      const payload = activityPayload(form);
      if (modal === "new") await activitiesApi.create(payload);
      else await activitiesApi.update(form.id, payload);
      toast.success(`${form.activity_type} saved`);
      setModal(null); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  // Visit / Call Reports are never deleted: cancelled with a reason and kept on record.
  const cancelActivity = async (a) => {
    const reason = await reasonDialog({ title: `Cancel ${a.activity_type}`, confirmLabel: "Cancel report",
      message: "The report will be marked Cancelled and kept on record." });
    if (!reason) return;
    try { await activitiesApi.cancel(a.id, reason); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Cancel failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <PageHeader title="Call Reports / Contact Notes"
        subtitle={`${activities.length} report${activities.length === 1 ? "" : "s"}`}
        actions={<>
<div className="flex gap-2">
          <button onClick={() => openNew("Visit Report")} className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 hover:opacity-90" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={14} /> Visit Report
          </button>
          <button onClick={() => openNew("Call Report")} className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 hover:opacity-90" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={14} /> Call Report
          </button>
        </div>
        </>} />

      <div className="flex gap-2 flex-wrap items-center">
        {["All", ...ACTIVITY_TYPES].map((t) => (
          <button key={t} onClick={() => setTypeFilter(t)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${typeFilter === t ? "text-white border-transparent" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
            style={typeFilter === t ? { background: "#1a3a5c" } : {}}>
            {t}
          </button>
        ))}
        <select value={clientFilter} onChange={(e) => setClientFilter(e.target.value)}
          className="ml-auto border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-brand-400">
          <option value="">All clients</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.company_name}</option>)}
        </select>
      </div>

      <div className="space-y-3">
        {filtered.length === 0 && <p className="text-sm text-gray-400 text-center py-8">No visit or call reports.</p>}
        {filtered.map((a) => (
          <ActivityCard key={a.id} activity={a} onEdit={() => { setForm({ ...blankActivity(), ...a, account_id: a.account_id || "" }); setModal("edit"); }}
            onCancel={a.status !== "Cancelled" ? () => cancelActivity(a) : undefined} />
        ))}
      </div>

      {modal && (
        <Modal title={modal === "new" ? `New ${form.activity_type}` : `Edit ${form.activity_uid}`} onClose={() => setModal(null)}>
          <ActivityForm form={form} setForm={setForm} accounts={accounts} />
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

