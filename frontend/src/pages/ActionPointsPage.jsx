import React, { useEffect, useMemo, useState } from "react";
import { actionPointsApi, casesApi, usersApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";
import { ACTION_POINT_STATUS_OPTIONS, ACTION_POINT_PRIORITY_OPTIONS } from "../utils/constants";

const NEXT = { Open: "In Progress", "In Progress": "Done", Done: null };
const PREV = { Done: "In Progress", "In Progress": "Open", Open: null };

export default function ActionPointsPage() {
  const user = useAuthStore((s) => s.user);
  const [items, setItems] = useState([]);
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [aps, cs, us] = await Promise.all([
        actionPointsApi.list(),
        casesApi.list({ limit: 500 }),
        usersApi.list(),
      ]);
      setItems(aps || []);
      setCases(cs.items || []);
      setUsers(us || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load action points");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const caseById = useMemo(() => Object.fromEntries(cases.map((c) => [c.id, c])), [cases]);
  const userById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users]);

  const openNew = () => { setForm({ title: "", detail: "", case_id: "", owner_id: "", priority: "Medium", due_date: "" }); setModal(true); };
  const openEdit = (ap) => { setForm({ ...ap, case_id: ap.case_id ?? "", owner_id: ap.owner_id ?? "", due_date: ap.due_date ?? "" }); setModal(true); };

  const save = async () => {
    const payload = {
      title: form.title, detail: form.detail || null, priority: form.priority,
      case_id: form.case_id ? Number(form.case_id) : null,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
      due_date: form.due_date || null,
    };
    try {
      if (form.id) await actionPointsApi.update(form.id, payload);
      else await actionPointsApi.create(payload);
      setModal(false); load();
    } catch (e) { alert(e.response?.data?.detail || "Save failed"); }
  };

  const move = async (ap, status) => {
    try { await actionPointsApi.update(ap.id, { status }); load(); }
    catch (e) { alert(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (ap) => {
    if (!confirm(`Delete "${ap.title}"?`)) return;
    try { await actionPointsApi.remove(ap.id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Action Points</h1>
          <p className="text-sm text-gray-500">{items.length} open operational tasks (WIP board)</p>
        </div>
        <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={14} /> Add
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {ACTION_POINT_STATUS_OPTIONS.map((col) => {
          const colItems = items.filter((ap) => ap.status === col);
          return (
            <div key={col}>
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold text-gray-700">{col}</span>
                <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">{colItems.length}</span>
              </div>
              <div className="space-y-2 min-h-16">
                {colItems.map((ap) => (
                  <div key={ap.id} className="bg-white border border-gray-100 rounded-xl p-3 shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <button onClick={() => openEdit(ap)} className="text-xs font-semibold text-gray-800 text-left hover:text-blue-600">{ap.title}</button>
                      <Badge text={ap.priority} />
                    </div>
                    {ap.detail && <p className="text-xs text-gray-500 mt-1 line-clamp-2">{ap.detail}</p>}
                    <div className="text-[11px] text-gray-400 mt-2 space-y-0.5">
                      {ap.case_id && <div>{caseById[ap.case_id]?.company_name || `Case #${ap.case_id}`}</div>}
                      <div className="flex gap-2">
                        {ap.owner_id && <span>{userById[ap.owner_id]?.name || `User #${ap.owner_id}`}</span>}
                        {ap.due_date && <span>· due {ap.due_date}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 mt-2" onClick={(e) => e.stopPropagation()}>
                      {PREV[ap.status] && (
                        <button onClick={() => move(ap, PREV[ap.status])} className="text-xs px-2 py-0.5 rounded border border-gray-200 text-gray-500 hover:bg-gray-50">‹ {PREV[ap.status]}</button>
                      )}
                      {NEXT[ap.status] && (
                        <button onClick={() => move(ap, NEXT[ap.status])} className="text-xs px-2 py-0.5 rounded border border-gray-200 text-gray-500 hover:bg-gray-50">{NEXT[ap.status]} ›</button>
                      )}
                      <button onClick={() => remove(ap)} className="ml-auto p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                        <Icon name="del" size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {modal && (
        <Modal title={form.id ? "Edit Action Point" : "New Action Point"} onClose={() => setModal(false)}>
          <Field label="Title" required><Input value={form.title || ""} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} /></Field>
          <Field label="Detail"><Textarea value={form.detail || ""} onChange={(e) => setForm((p) => ({ ...p, detail: e.target.value }))} /></Field>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Entity (optional)">
              <Select value={form.case_id || ""} onChange={(e) => setForm((p) => ({ ...p, case_id: e.target.value }))}>
                <option value="">— None —</option>
                {cases.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Owner">
              <Select value={form.owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, owner_id: e.target.value }))}>
                <option value="">— Unassigned —</option>
                {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            <Field label="Priority">
              <Select value={form.priority || "Medium"} onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}>
                {ACTION_POINT_PRIORITY_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            <Field label="Due Date"><Input type="date" value={form.due_date || ""} onChange={(e) => setForm((p) => ({ ...p, due_date: e.target.value }))} /></Field>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
