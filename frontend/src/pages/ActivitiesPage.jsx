import React, { useEffect, useState } from "react";
import { activitiesApi, casesApi, usersApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";

const TYPE_COLORS = {
  Meeting: "#2B6D9A", Demo: "#8b5cf6", Call: "#10b981",
  Email: "#94a3b8", "Follow-up": "#f59e0b", Note: "#64748b",
};

export default function ActivitiesPage() {
  const [activities, setActivities] = useState([]);
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [typeFilter, setTypeFilter] = useState("All");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [actRes, caseRes, usersRes] = await Promise.all([
        activitiesApi.list({ limit: 500 }),
        casesApi.list({ limit: 500 }),
        usersApi.list(),
      ]);
      setActivities(actRes.items || []);
      setCases(caseRes.items || []);
      setUsers(usersRes || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load activities");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const filtered = activities.filter((a) => typeFilter === "All" || a.activity_type === typeFilter);

  const openNew = () => {
    const first = cases[0];
    setForm({
      case_id: first?.id, company_name: first?.company_name || "",
      activity_date: new Date().toISOString().split("T")[0], activity_type: "Call",
      status: "Planned", summary: "", outcome: "", next_action: "",
    });
    setModal("new");
  };

  const save = async () => {
    try {
      const c = cases.find((x) => x.id === Number(form.case_id));
      const payload = { ...form, case_id: Number(form.case_id), company_name: c?.company_name || form.company_name };
      if (modal === "new") {
        await activitiesApi.create(payload);
      } else {
        const { id, activity_uid, created_at, updated_at, ...patch } = payload;
        await activitiesApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this activity?")) return;
    try { await activitiesApi.delete(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Activities</h1>
          <p className="text-sm text-gray-500">{activities.length} total activities</p>
        </div>
        <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={14} /> Log Activity
        </button>
      </div>

      <div className="flex gap-2 flex-wrap">
        {["All", "Meeting", "Demo", "Call", "Email", "Follow-up"].map((t) => (
          <button key={t} onClick={() => setTypeFilter(t)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${typeFilter === t ? "text-white border-transparent" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
            style={typeFilter === t ? { background: "#2B6D9A" } : {}}>
            {t}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.length === 0 && <p className="text-sm text-gray-400 text-center py-8">No activities.</p>}
        {filtered.map((a) => (
          <div key={a.id} className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow flex gap-4">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold"
                style={{ background: TYPE_COLORS[a.activity_type] || "#94a3b8" }}>
                {a.activity_type[0]}
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm text-gray-800">{a.company_name}</span>
                  <Badge text={a.activity_type} />
                  <span className="text-xs text-gray-400">{a.activity_uid}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400 whitespace-nowrap">{a.activity_date}</span>
                  <button onClick={() => { setForm(a); setModal("edit"); }}
                    className="p-1 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600">
                    <Icon name="edit" size={13} />
                  </button>
                  <button onClick={() => remove(a.id)}
                    className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                    <Icon name="del" size={13} />
                  </button>
                </div>
              </div>
              <p className="text-sm text-gray-700 mb-1">{a.summary}</p>
              <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                {a.outcome && <span><strong className="text-gray-600">Outcome:</strong> {a.outcome}</span>}
                {a.next_action && <span><strong className="text-gray-600">Next:</strong> {a.next_action}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {modal && (
        <Modal title={modal === "new" ? "Log Activity" : `Edit ${form.activity_uid}`} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Case" required>
              <Select value={form.case_id || ""} onChange={(e) => setForm((p) => ({ ...p, case_id: e.target.value }))}>
                {cases.map((c) => <option key={c.id} value={c.id}>{c.case_uid} – {c.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Activity Type" required>
              <Select value={form.activity_type || "Call"} onChange={(e) => setForm((p) => ({ ...p, activity_type: e.target.value }))}>
                {["Meeting", "Demo", "Call", "Email", "Follow-up", "Note"].map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Date" required>
              <Input type="date" value={form.activity_date || ""} onChange={(e) => setForm((p) => ({ ...p, activity_date: e.target.value }))} />
            </Field>
            <Field label="Status">
              <Select value={form.status || "Planned"} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {["Planned", "Completed", "Cancelled", "Overdue"].map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Summary" required><Textarea value={form.summary || ""} onChange={(e) => setForm((p) => ({ ...p, summary: e.target.value }))} /></Field>
          <Field label="Outcome"><Textarea value={form.outcome || ""} onChange={(e) => setForm((p) => ({ ...p, outcome: e.target.value }))} /></Field>
          <Field label="Next Action"><Input value={form.next_action || ""} onChange={(e) => setForm((p) => ({ ...p, next_action: e.target.value }))} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
