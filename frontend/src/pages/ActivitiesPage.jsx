import React, { useEffect, useState } from "react";
import { activitiesApi, accountsApi, casesApi } from "../api/endpoints";
import { Icon, Modal, Spinner, ErrorBanner } from "../components/ui";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";
import ActivityForm, { ACTIVITY_TYPES, REPORT_TYPES, activityPayload, activityProblem, blankActivity } from "../components/activities/ActivityForm";
import ActivityCard from "../components/activities/ActivityCard";

/** Activities, Visit Reports and Call Reports across all the clients this user can see (BRD §17). */
export default function ActivitiesPage() {
  const [activities, setActivities] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [typeFilter, setTypeFilter] = useState("All");
  const [clientFilter, setClientFilter] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [actRes, accRes, caseRes] = await Promise.all([
        activitiesApi.list({ limit: 500 }), accountsApi.list({ limit: 500 }), casesApi.list({ limit: 500 }),
      ]);
      setActivities(actRes.items || []);
      setAccounts(accRes.items || []);
      setCases(caseRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load activities");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = activities.filter((a) => (typeFilter === "All" || (typeFilter === "Reports" ? REPORT_TYPES.includes(a.activity_type) : a.activity_type === typeFilter))
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

  const remove = async (id) => {
    if (!(await confirmDialog("Delete this activity?"))) return;
    try { await activitiesApi.delete(id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Activities</h1>
          <p className="text-sm text-gray-500">Visit Reports, Call Reports and other client activities · {activities.length} in total</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => openNew("Visit Report")} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={14} /> Visit Report
          </button>
          <button onClick={() => openNew("Call Report")} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={14} /> Call Report
          </button>
          <button onClick={() => openNew("Meeting")} className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg flex items-center gap-1 text-gray-600 hover:bg-gray-50">
            <Icon name="plus" size={14} /> Other activity
          </button>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        {["All", "Reports", ...ACTIVITY_TYPES].map((t) => (
          <button key={t} onClick={() => setTypeFilter(t)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${typeFilter === t ? "text-white border-transparent" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
            style={typeFilter === t ? { background: "#1a3a5c" } : {}}>
            {t === "Reports" ? "Visit & Call Reports" : t}
          </button>
        ))}
        <select value={clientFilter} onChange={(e) => setClientFilter(e.target.value)}
          className="ml-auto border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-brand-400">
          <option value="">All clients</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.company_name}</option>)}
        </select>
      </div>

      <div className="space-y-3">
        {filtered.length === 0 && <p className="text-sm text-gray-400 text-center py-8">No activities.</p>}
        {filtered.map((a) => (
          <ActivityCard key={a.id} activity={a} onEdit={() => { setForm({ ...blankActivity(), ...a, account_id: a.account_id || "", case_id: a.case_id || "" }); setModal("edit"); }}
            onDelete={() => remove(a.id)} />
        ))}
      </div>

      {modal && (
        <Modal title={modal === "new" ? `New ${form.activity_type}` : `Edit ${form.activity_uid}`} onClose={() => setModal(null)}>
          <ActivityForm form={form} setForm={setForm} accounts={accounts} cases={cases} />
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

