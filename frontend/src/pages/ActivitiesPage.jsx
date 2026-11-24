import React, { useEffect, useRef, useState } from "react";
import { activitiesApi, accountsApi, usersApi } from "../api/endpoints";
import { DateInput, FilterBar, Icon, PageHeader, SearchInput, Select, Spinner, ErrorBanner } from "../components/ui";
import { Pager, usePageSize } from "../components/listing";
import { toast } from "../store/toast";
import { useAuthStore } from "../store/auth";
import { reasonDialog } from "../store/confirm";
import { ACTIVITY_TYPES, blankActivity } from "../components/activities/ActivityForm";
import ActivityCard from "../components/activities/ActivityCard";
import ReportDialog from "../components/activities/ReportDialog";
import ClientPicker from "../components/ClientPicker";

/**
 * Visit Reports and Call Reports across all the clients this user can see (BRD §15). Triam 23-11-2026: every past
 * report can be found and reviewed at any time: the list is paged on the server (nothing is cut off) and filtered
 * by text, type, client, writer, state and date.
 */
export default function ActivitiesPage() {
  const readOnly = useAuthStore((s) => s.isReadOnly());
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [accounts, setAccounts] = useState([]);
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [f, setF] = useState({ activity_type: "", account_id: "", owner_id: "", status: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = usePageSize("callReports", 15);
  const [open, setOpen] = useState(null); // the report in the dialog
  const latest = useRef(0);

  useEffect(() => { const t = setTimeout(() => setQuery(search.trim()), 300); return () => clearTimeout(t); }, [search]);
  useEffect(() => {
    accountsApi.list({ limit: 1000 }).then((r) => setAccounts(r.items || [])).catch(() => {});
    usersApi.list().then((u) => setUsers(u || [])).catch(() => {});
  }, []);

  const load = async () => {
    const ticket = ++latest.current;
    setBusy(true);
    try {
      const params = { skip: page * pageSize, limit: pageSize, search: query || undefined,
        ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) };
      const r = await activitiesApi.list(params);
      if (ticket !== latest.current) return;
      setItems(r.items || []); setTotal(r.total || 0); setError(null);
    } catch (e) {
      if (ticket === latest.current) setError(e.response?.data?.detail || "Failed to load visit and call reports");
    } finally { if (ticket === latest.current) setBusy(false); }
  };
  useEffect(() => { setPage(0); }, [query, f, pageSize]);
  useEffect(() => { load(); }, [page, query, f, pageSize]);

  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  const cancelReport = async (a) => {
    const reason = await reasonDialog({ title: `Cancel ${a.activity_type}`, confirmLabel: "Cancel report",
      message: "The report will be marked Cancelled and kept on record." });
    if (!reason) return;
    try { await activitiesApi.cancel(a.id, reason); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Cancel failed"); }
  };
  const writers = users.filter((u) => u.is_active !== false && u.role !== "admin" && !u.person_id);
  const filtering = query || Object.values(f).some(Boolean);

  if (error && items === null) return <ErrorBanner message={error} onRetry={load} />;
  if (items === null) return <Spinner />;

  return (
    <div className="space-y-4">
      <PageHeader title="Call Reports / Contact Notes"
        subtitle={`${total} report${total === 1 ? "" : "s"}${filtering ? " match these filters" : ""}`}
        actions={!readOnly && (
          // Triam 24-11-2026: one button; Visit or Call is chosen in the form (Type).
          <button onClick={() => setOpen(blankActivity(f.account_id, f.activity_type || "Visit Report"))}
            className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 bg-brand-600 hover:bg-brand-700">
            <Icon name="plus" size={14} /> New Report
          </button>
        )} />

      <FilterBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search client, contact or discussion…" />
        <div className="w-36"><Select aria-label="Filter by type" value={f.activity_type} onChange={set("activity_type")}>
          <option value="">All types</option>{ACTIVITY_TYPES.map((t) => <option key={t}>{t}</option>)}
        </Select></div>
        <div className="w-64"><ClientPicker aria-label="Filter by client" clients={accounts} allLabel="All clients" value={f.account_id}
          onChange={(v) => setF((p) => ({ ...p, account_id: v }))} /></div>
        <div className="w-44"><Select aria-label="Filter by writer" value={f.owner_id} onChange={set("owner_id")}>
          <option value="">Everyone</option>{writers.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </Select></div>
        <div className="w-36"><Select aria-label="Filter by state" value={f.status} onChange={set("status")}>
          <option value="">Draft and final</option>{["Draft", "Final", "Cancelled"].map((s) => <option key={s}>{s}</option>)}
        </Select></div>
        <div className="w-40"><DateInput aria-label="From date" placeholder="From DD MM YYYY" value={f.date_from} onChange={set("date_from")} /></div>
        <div className="w-40"><DateInput aria-label="To date" placeholder="To DD MM YYYY" value={f.date_to} onChange={set("date_to")} /></div>
      </FilterBar>

      <div className={`space-y-3 ${busy ? "opacity-60" : ""}`}>
        {items.length === 0 && <p className="text-sm text-gray-500 text-center py-8">{filtering ? "No reports match these filters." : "No visit or call reports yet."}</p>}
        {items.map((a) => (
          <ActivityCard key={a.id} activity={a} onOpen={() => setOpen({ ...blankActivity(), ...a, account_id: a.account_id || "" })}
            onCancel={!readOnly && a.status !== "Cancelled" ? () => cancelReport(a) : undefined} />
        ))}
      </div>
      <Pager page={page} pageSize={pageSize} total={total} onPage={setPage} onPageSize={setPageSize} busy={busy} label="Reports" />

      {open && <ReportDialog report={open} accounts={accounts} readOnly={readOnly} onClose={() => setOpen(null)}
        onSaved={() => { setOpen(null); load(); }} />}
    </div>
  );
}
