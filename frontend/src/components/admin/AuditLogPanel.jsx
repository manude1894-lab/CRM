import React, { useEffect, useState } from "react";
import { auditApi } from "../../api/endpoints";
import { Select, Input } from "../ui";
import AuditTrail from "../AuditTrail";
import { toast } from "../../store/toast";

const PAGE = 50;
const SUBJECTS = ["Account", "AccountParty", "Document", "Case", "User", "Role", "Department", "MasterItem"];
const ACTIONS = ["create", "update", "delete", "login", "login_failed"];

// BRD §15 — global, read-only audit log for admins / users with audit.view.
export default function AuditLogPanel({ users }) {
  const [filters, setFilters] = useState({ subject_type: "", action: "", user_id: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(0);
  const [data, setData] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
    setLoading(true);
    auditApi.list({ ...params, skip: page * PAGE, limit: PAGE })
      .then(setData)
      .catch((e) => toast.error(e.response?.data?.detail || "Failed to load audit log"))
      .finally(() => setLoading(false));
  }, [filters, page]);

  const set = (k) => (e) => { setPage(0); setFilters((f) => ({ ...f, [k]: e.target.value })); };
  const pages = Math.max(1, Math.ceil(data.total / PAGE));

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
      <div className="flex flex-wrap items-end gap-2 mb-4">
        <Select value={filters.subject_type} onChange={set("subject_type")} className="text-xs !w-auto">
          <option value="">All records</option>
          {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
        </Select>
        <Select value={filters.action} onChange={set("action")} className="text-xs !w-auto">
          <option value="">All actions</option>
          {ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
        </Select>
        <Select value={filters.user_id} onChange={set("user_id")} className="text-xs !w-auto">
          <option value="">All users</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </Select>
        <Input type="date" value={filters.date_from} onChange={set("date_from")} className="text-xs !w-auto" title="From" />
        <Input type="date" value={filters.date_to} onChange={set("date_to")} className="text-xs !w-auto" title="To" />
        <span className="text-xs text-gray-400 ml-auto">{data.total} entr{data.total === 1 ? "y" : "ies"}</span>
      </div>
      <AuditTrail entries={data.items} loading={loading} emptyText="No audit entries match these filters." />
      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 mt-3 text-xs">
          <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="px-2 py-1 border border-gray-200 rounded disabled:opacity-40">Previous</button>
          <span className="text-gray-500">Page {page + 1} of {pages}</span>
          <button disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)} className="px-2 py-1 border border-gray-200 rounded disabled:opacity-40">Next</button>
        </div>
      )}
    </div>
  );
}
