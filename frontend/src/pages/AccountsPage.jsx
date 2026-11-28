import React, { useEffect, useRef, useState } from "react";
import { accountsApi, usersApi, countriesApi, prospectsApi } from "../api/endpoints";
import { Badge, Button, EmptyState, ErrorBanner, FilterBar, Icon, Modal, PageHeader, SearchInput, Select, Spinner } from "../components/ui";
import AccountCard from "../components/accounts/AccountCard";
import AccountFormModal from "../components/accounts/AccountFormModal";
import BulkActionBar from "../components/accounts/BulkActionBar";
import ImportPreviewModal from "../components/accounts/ImportPreviewModal";
import ClientProfilePage from "./ClientProfilePage";
import { Pager, SortTh, usePageSize } from "../components/listing";
import { BLANK_ACCOUNT_FORM } from "../components/accounts/accountForm";
import { buildAccountsCsv, parseImportRows } from "../components/accounts/accountCsv";
import { toast } from "../store/toast";
import { fmtDate, exportFilename, statusReason, WITH_RM_STATUSES, PARKED_STATUSES } from "../utils/constants";
import { useAuthStore } from "../store/auth";

const BLANK_BULK = { spoc_id: "", risk_rating: "" };
// Triam input 19-10-2026: clients being onboarded and existing clients are separate menu items.
const SCOPES = {
  onboarding: {
    title: "New Client Onboarding", statuses: [...WITH_RM_STATUSES, "Awaiting Approval", ...PARKED_STATUSES],
    subtitle: (n) => `${n} client${n === 1 ? "" : "s"} being onboarded`,
    empty: "Clients appear here once they are created from a prospect sent to the RM.",
  },
  maintenance: {
    title: "Client Data Maintenance", statuses: ["Approved", "Active", "Inactive", "Marked for Exit", "Exited"],
    subtitle: (n) => `${n} existing client${n === 1 ? "" : "s"}`,
    empty: "Clients appear here once the Approver has approved them, or when they are imported.",
  },
};
const VIEW_KEY = "triam.clients.view";
// Triam 13-11-2026: approved clients are listed with the latest approval on top, and can be filtered by
// when they were approved.
const APPROVED_WITHIN = { "": "Approved: any time", 7: "Approved in the last 7 days", 30: "Approved in the last 30 days",
  90: "Approved in the last 90 days", year: "Approved this year" };
// The card view has no column headers, so it keeps a sort list; the table sorts by clicking a header (Triam
// 22-11-2026). Each entry is the server's sort: a column, "-" in front for the reverse order.
const SORTS = { "-approved": "Latest approval first", name: "Client name A–Z", aml: "Next AML review first" };
const sortParam = (s) => (s.dir === "desc" ? `-${s.by}` : s.by);
const sortFromParam = (v) => (v.startsWith("-") ? { by: v.slice(1), dir: "desc" } : { by: v, dir: "asc" });
const approvedSince = (key) => {
  if (!key) return null;
  const now = new Date();
  return key === "year" ? new Date(now.getFullYear(), 0, 1) : new Date(now.getTime() - Number(key) * 86400000);
};

// Triam 28-11-2026: on a phone the list opens as cards (the table needs sideways scrolling there).
const defaultView = () => (typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches ? "cards" : "table");
const readView = () => { try { return localStorage.getItem(VIEW_KEY) || defaultView(); } catch { return defaultView(); } };

export default function AccountsPage({ scope = "onboarding", initialAccountId, initialOpenForm, initialProspectId, initialStatus, onNavigate } = {}) {
  const cfg = SCOPES[scope];
  const appliedInitialRef = useRef(false);
  const [accounts, setAccounts] = useState([]); // the current page of clients, filtered and sorted by the server
  // Review 22-11-2026 (package 4): lists are paged on the server; the page size is the user's choice.
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0); // clients matching the filters
  const [liveTotal, setLiveTotal] = useState(0); // all clients of this menu item, Dropped aside
  const [listLoading, setListLoading] = useState(false);
  const [users, setUsers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  // Opened from a dashboard lifecycle stage: start filtered to that status.
  const [statusFilter, setStatusFilter] = useState(() => (initialStatus && SCOPES[scope].statuses.includes(initialStatus) ? initialStatus : ""));
  const [riskFilter, setRiskFilter] = useState("");
  const [approvedWithin, setApprovedWithin] = useState("");
  const [sort, setSort] = useState(scope === "maintenance" ? { by: "approved", dir: "desc" } : { by: "name", dir: "asc" });
  const sortBy = sortParam(sort);
  const [pageSize, setPageSize] = usePageSize(`clients.${scope}`, 50);
  // Triam 22-11-2026: New Client Onboarding shows either the clients or the prospects waiting for one, not both.
  const [tab, setTab] = useState("clients");
  const [view, setView] = useState(readView);
  const [open, setOpen] = useState(null); // { id, tab } — the client page being shown
  // BRD §4A — a client is created only from an assigned prospect: "Create client" on the prospect
  // lands here with the prospect chosen.
  const [newClient, setNewClient] = useState(null); // { key, prospect }
  useEffect(() => {
    if (initialProspectId) prospectsApi.get(initialProspectId).then((p) => setNewClient({ key: Date.now(), prospect: p })).catch(() => {});
  }, [initialProspectId]);
  const [importPreview, setImportPreview] = useState(null);
  const [importing, setImporting] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkValues, setBulkValues] = useState(BLANK_BULK);
  const [bulkApplying, setBulkApplying] = useState(false);
  const fileInputRef = useRef(null);
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const me = useAuthStore((s) => s.user);
  const canAssign = useAuthStore((s) => s.isProspectCoordinator());
  const readOnly = useAuthStore((s) => s.isReadOnly());
  const [prospects, setProspects] = useState([]);
  const [shownProspect, setShownProspect] = useState(null);

  // The server applies the filters: this menu item's statuses (Dropped only when picked or searched for), the
  // search, the risk level, the approval date and the sort.
  const liveStatuses = cfg.statuses.filter((st) => st !== "Dropped");
  const [query, setQuery] = useState(""); // the search, applied 300 ms after typing stops
  useEffect(() => { const t = setTimeout(() => setQuery(search.trim()), 300); return () => clearTimeout(t); }, [search]);
  const listParams = (extra = {}) => {
    const since = scope === "maintenance" ? approvedSince(approvedWithin) : null;
    return {
      statuses: (statusFilter ? [statusFilter] : query ? cfg.statuses : liveStatuses).join(","),
      search: query || undefined, risk: riskFilter || undefined,
      approved_since: since ? since.toISOString().slice(0, 10) : undefined,
      sort: sortBy, ...extra,
    };
  };

  // Only the latest request's answer is shown: changing a filter on page 2 also returns to page 1, and the answer
  // for the old page must not land after the new one.
  const latestList = useRef(0);
  const loadList = async () => {
    const mine = ++latestList.current;
    setListLoading(true);
    try {
      const [res, live] = await Promise.all([
        accountsApi.list(listParams({ skip: page * pageSize, limit: pageSize })),
        accountsApi.list({ statuses: liveStatuses.join(","), limit: 1 }),
      ]);
      if (mine !== latestList.current) return;
      setAccounts(res.items || []); setTotal(res.total || 0); setLiveTotal(live.total || 0);
    } catch (e) {
      if (mine === latestList.current) setError(e.response?.data?.detail || "Failed to load clients");
    } finally { if (mine === latestList.current) setListLoading(false); }
  };
  // `silent` refreshes in the background without the full-page spinner.
  const load = async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const [usersRes, countriesRes, prospectRes] = await Promise.all([
        usersApi.list(), countriesApi.list().catch(() => []),
        scope === "onboarding" ? prospectsApi.list().catch(() => []) : Promise.resolve([]),
        loadList(),
      ]);
      setProspects(prospectRes || []);
      setUsers(usersRes || []);
      setCountries(countriesRes || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load clients");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  // A new filter starts again at the first page; a page or filter change reloads the list.
  useEffect(() => { setPage(0); }, [query, statusFilter, riskFilter, approvedWithin, sortBy, pageSize]);
  // A new page of the list starts at its top.
  useEffect(() => { if (page > 0 || !firstRun.current) document.getElementById('main-content')?.scrollTo?.({ top: 0 }); }, [page]);
  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) { firstRun.current = false; return; }
    loadList();
  }, [page, query, statusFilter, riskFilter, approvedWithin, sortBy, pageSize]);

  // Arriving from elsewhere (e.g. "Review" in the Compliance inbox) opens that client's page. The client is read
  // directly: with paging it may not be on the first page of the list.
  useEffect(() => {
    if (appliedInitialRef.current || !initialAccountId) return;
    appliedInitialRef.current = true;
    accountsApi.get(initialAccountId).then((target) => {
      if (!cfg.statuses.includes(target.profile_status || "New")) {
        onNavigate?.({ page: scope === "onboarding" ? "maintenance" : "accounts", accountId: target.id, openForm: initialOpenForm });
        return;
      }
      setOpen({ id: initialAccountId, tab: initialOpenForm ? "profile" : "overview" });
    }).catch(() => toast.error("That client could not be opened"));
  }, [initialAccountId]);

  const changeView = (v) => { setView(v); try { localStorage.setItem(VIEW_KEY, v); } catch { /* ignore */ } };
  const userName = (id) => users.find((u) => u.id === id)?.name || "—";

  const toggleSelected = (id) => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const toggleSelectAll = (ids) => setSelectedIds((prev) => (ids.every((id) => prev.has(id)) ? new Set() : new Set(ids)));

  const applyBulkField = async (field) => {
    const value = bulkValues[field];
    if (!value || selectedIds.size === 0) return;
    setBulkApplying(true);
    try {
      const results = await accountsApi.bulkUpdate({ ids: [...selectedIds], [field]: field === "spoc_id" ? +value : value });
      const failed = results.filter((r) => r.status === "error");
      toast[failed.length === 0 ? "success" : "error"](failed.length === 0
        ? `Updated ${results.length} client${results.length !== 1 ? "s" : ""}.`
        : `Updated ${results.length - failed.length}/${results.length}. ${failed.length} not changed (e.g. approved clients need an amendment).`);
      setSelectedIds(new Set());
      setBulkValues(BLANK_BULK);
      load({ silent: true });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Bulk update failed");
    } finally { setBulkApplying(false); }
  };

  // Every client matching the filters, not only the page on screen.
  const exportCSV = async () => {
    try {
      const all = [];
      for (let skip = 0; ; skip += 1000) {
        const res = await accountsApi.list(listParams({ skip, limit: 1000 }));
        all.push(...(res.items || []));
        if (all.length >= (res.total || 0) || !(res.items || []).length) break;
      }
      const a = document.createElement("a");
      // A UTF-8 marker first, so Excel shows accents, dashes and Arabic names correctly (Triam 23-11-2026).
      a.href = URL.createObjectURL(new Blob(["\uFEFF" + buildAccountsCsv(all, users)], { type: "text/csv;charset=utf-8" }));
      a.download = exportFilename("clients"); a.click();
    } catch (e) { toast.error(e.response?.data?.detail || "Export failed"); }
  };

  const handleImportFile = async (file) => {
    const parsed = parseImportRows(await file.text(), users);
    if (parsed.length === 0) { toast.error("No rows with a Company Name found in that CSV."); return; }
    try {
      setImporting(true);
      const res = await accountsApi.import(parsed, true);
      setImportPreview({ rows: parsed, ...res });
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to preview import");
    } finally { setImporting(false); }
  };

  const confirmImport = async () => {
    if (!importPreview) return;
    try {
      setImporting(true);
      await accountsApi.import(importPreview.rows, false);
      setImportPreview(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Import failed");
    } finally { setImporting(false); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  if (open) {
    return (
      <ClientProfilePage key={open.id} accountId={open.id} initialTab={open.tab} users={users} countries={countries} backLabel={cfg.title}
        onBack={() => { setOpen(null); load({ silent: true }); }} onChanged={() => load({ silent: true })} />
    );
  }

  // The server returns this menu item's clients, filtered and sorted (Triam input 19-10-2026; UAT 18-11-2026:
  // a dropped client leaves the working list, shown when Dropped is picked or searched for).
  const filtered = accounts;
  const ids = filtered.map((a) => a.id);
  const openClient = (a) => setOpen({ id: a.id, tab: "overview" });
  // Prospects sent to an RM and still waiting for their client: the RM sees their own, the Prospecting
  // Coordinator and administrators see all. Newest first (Triam input 19-10-2026).
  const waiting = prospects
    .filter((p) => p.owner_id && !p.converted_account_id && p.status !== "Dropped" && (isAdmin || p.owner_id === me?.id || canAssign))
    .sort((x, y) => String(y.assigned_at || y.created_at).localeCompare(String(x.assigned_at || x.created_at)));
  const createFrom = (p) => { setShownProspect(null); setNewClient({ key: Date.now(), prospect: p }); };

  return (
    <div className="space-y-4">
      <PageHeader title={cfg.title} subtitle={cfg.subtitle(liveTotal)}
        actions={<>
          {isAdmin && <Button onClick={exportCSV}>Export CSV</Button>}
          {isAdmin && scope === "maintenance" && (
            <>
              <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ""; }} />
              <Button onClick={() => fileInputRef.current?.click()} disabled={importing}>{importing ? "Reading…" : "Import CSV"}</Button>
            </>
          )}
          {scope === "onboarding" && !readOnly && <Button variant="primary" onClick={() => onNavigate?.({ page: "prospects" })}>Go to Prospects</Button>}
        </>}
      />

      {scope === "onboarding" && (
        <div role="tablist" aria-label="Show" className="flex gap-1 border-b border-gray-200">
          {[["clients", "Clients being onboarded", liveTotal], ["prospects", isAdmin || canAssign ? "Prospects waiting for a client" : "My prospects waiting for a client", waiting.length]].map(([k, label, n]) => (
            <button key={k} role="tab" type="button" aria-selected={tab === k} onClick={() => setTab(k)}
              className={`-mb-px px-4 py-2.5 text-sm border-b-2 flex items-center gap-2 ${tab === k ? "border-brand-600 text-brand-700 font-semibold" : "border-transparent text-gray-600 hover:text-gray-900"}`}>
              {label}
              <span className={`min-w-[22px] px-1.5 py-0.5 rounded-full text-[11px] font-semibold text-center ${k === "prospects" && n > 0 ? "bg-gold text-brand-900" : "bg-gray-100 text-gray-600"}`}>{n}</span>
            </button>
          ))}
        </div>
      )}

      {scope === "onboarding" && tab === "prospects" && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <div className="px-4 py-3 border-b border-gray-100 text-sm font-semibold text-gray-800">
            {isAdmin || canAssign ? "Prospects sent to RMs" : "Prospects sent to me"}
            <span className="ml-2 text-xs font-normal text-gray-500">{waiting.length} waiting for the client to be created</span>
          </div>
          {waiting.length === 0 ? <p className="px-4 py-5 text-sm text-gray-500">No prospects waiting.</p> : (
            <table className="w-full text-sm">
              <thead><tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                {["Date Sent", "Prospect Name", "Contact Name", "Contact Phone", "Contact Email", "Services the prospect is looking for"].map((h) => (
                  <th key={h} className="py-2.5 px-3 font-semibold text-left">{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {waiting.map((p) => (
                  <tr key={p.id} className="border-b border-gray-50 align-top">
                    <td className="py-2.5 px-3 text-xs text-gray-600 whitespace-nowrap">{fmtDate(p.assigned_at || p.created_at)}</td>
                    <td className="py-2.5 px-3">
                      <button onClick={() => setShownProspect(p)} className="font-medium text-brand-700 hover:underline text-left">{p.company_name}</button>
                      <div className="text-[11px] text-gray-500 font-mono">{p.prospect_uid}{isAdmin || p.owner_id !== me?.id ? ` · ${userName(p.owner_id)}` : ""}</div>
                    </td>
                    <td className="py-2.5 px-3 text-xs text-gray-600">{p.contact_name || "—"}</td>
                    <td className="py-2.5 px-3 text-xs text-gray-600">{p.contact_phone || "—"}</td>
                    <td className="py-2.5 px-3 text-xs text-gray-600">{p.contact_email || "—"}</td>
                    <td className="py-2.5 px-3 text-xs text-gray-600 max-w-xs">{p.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {(scope !== "onboarding" || tab === "clients") && (<>
      <FilterBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search by client name or Client ID…" />
        <div className="w-60"><Select aria-label="Filter by status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">{scope === "onboarding" ? "All statuses except Dropped" : "All statuses"}</option>
          {cfg.statuses.map((s) => <option key={s}>{s}</option>)}
        </Select></div>
        {/* Risk level and AML review are set by Compliance at approval, so only existing clients have them. */}
        {scope === "maintenance" && <div className="w-40"><Select aria-label="Filter by risk level" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
          <option value="">All risk levels</option>
          {["High", "Medium", "Low"].map((r) => <option key={r} value={r}>{r} risk</option>)}
        </Select></div>}
        {scope === "maintenance" && <div className="w-60"><Select aria-label="Approved within" value={approvedWithin} onChange={(e) => setApprovedWithin(e.target.value)}>
          {Object.entries(APPROVED_WITHIN).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </Select></div>}
        {view === "cards" && <div className="w-48"><Select aria-label="Sort" value={SORTS[sortBy] ? sortBy : ""} onChange={(e) => setSort(sortFromParam(e.target.value))}>
          {!SORTS[sortBy] && <option value="">Sorted by a column</option>}
          {Object.entries(SORTS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
        </Select></div>}
        <div className="ml-auto flex border border-gray-200 rounded-lg overflow-hidden bg-white">
          {[["table", "table", "Table"], ["cards", "kanban", "Cards"]].map(([v, icon, label]) => (
            <button key={v} onClick={() => changeView(v)}
              className={`px-3 py-1.5 text-xs flex items-center gap-1 ${view === v ? "bg-gray-100 text-gray-800 font-medium" : "text-gray-500 hover:bg-gray-50"}`}>
              <Icon name={icon} size={14} /> {label}
            </button>
          ))}
        </div>
      </FilterBar>

      {selectedIds.size > 0 && (
        <BulkActionBar count={selectedIds.size} users={users} values={bulkValues} onChange={setBulkValues}
          onApply={applyBulkField} applying={bulkApplying} onClear={() => setSelectedIds(new Set())} />
      )}

      {filtered.length === 0 ? (
        <EmptyState
          title={liveTotal === 0 && !query && !statusFilter ? `No clients in ${cfg.title}` : "No clients match these filters"}
          text={liveTotal === 0 && !query && !statusFilter ? cfg.empty : "Try a different search or clear the filters."} />
      ) : view === "table" ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                {!readOnly && <th className="py-2.5 px-3 w-8">
                  <input type="checkbox" aria-label="Select all clients" checked={ids.every((id) => selectedIds.has(id))} onChange={() => toggleSelectAll(ids)} />
                </th>}
                {(scope === "maintenance"
                  ? [["Client ID", "client_id"], ["Client", "name"], ["Status", "status"], ["Approved on", "approved", "desc"], ["Risk", "risk"],
                    ["Anchor RM", "rm"], ["PEP", "pep"], ["Next AML review", "aml"]]
                  : [["Client ID", "client_id"], ["Client", "name"], ["Status", "status"], ["Anchor RM", "rm"], ["PEP", "pep"]]
                ).map(([h, by, firstDir]) => <SortTh key={by} label={h} by={by} sort={sort} onSort={setSort} firstDir={firstDir} />)}
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} onClick={() => openClient(a)} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer">
                  {!readOnly && <td className="py-2.5 px-3" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" aria-label={`Select ${a.company_name}`} checked={selectedIds.has(a.id)} onChange={() => toggleSelected(a.id)} />
                  </td>}
                  <td className="py-2.5 px-3 font-mono text-xs text-gray-600">{a.client_id || <span className="text-gray-500" title="Temporary ID until the Final approval">{a.temp_id || a.account_uid}</span>}</td>
                  <td className="py-2.5 px-3">
                    <div className="font-medium text-gray-800">{a.company_name}</div>
                    <div className="text-xs text-gray-500">{a.account_type === "Individual" ? "Individual" : [a.client_category, a.country].filter(Boolean).join(" · ") || "Corporate"}{a.is_pep ? " · PEP" : ""}</div>
                  </td>
                  <td className="py-2.5 px-3">
                    <Badge text={a.profile_status || "New"} />
                    {a.approval_stage && <div className="text-[11px] text-amber-700 mt-0.5">{a.approval_stage === "Approver" ? "Pending with the Approver" : "Pending with Compliance"}</div>}
                    {statusReason(a) && <div className="text-[11px] text-gray-500 mt-0.5 max-w-[16rem] truncate" title={statusReason(a)}>{statusReason(a)}</div>}
                  </td>
                  {scope === "maintenance" && <td className="py-2.5 px-3 text-xs text-gray-600 whitespace-nowrap">{fmtDate(a.approved_at) || "—"}</td>}
                  {scope === "maintenance" && <td className="py-2.5 px-3 text-xs text-gray-600">{a.risk_rating || "—"}</td>}
                  <td className="py-2.5 px-3 text-xs text-gray-600">{userName(a.spoc_id)}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{a.is_pep ? "PEP" : "—"}</td>
                  {scope === "maintenance" && <td className="py-2.5 px-3 text-xs text-gray-600">{fmtDate(a.next_aml_review_date) || "—"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((a) => (
            <AccountCard key={a.id} account={a} anchorRm={userName(a.spoc_id)} isSelected={selectedIds.has(a.id)}
              onOpen={() => openClient(a)} onToggleSelected={() => toggleSelected(a.id)} />
          ))}
        </div>
      )}
      <Pager page={page} pageSize={pageSize} total={total} onPage={setPage} onPageSize={setPageSize} busy={listLoading} label="Clients" />
      </>)}

      {newClient && (
        <AccountFormModal key={newClient.key} users={users} countries={countries}
          initialForm={{ ...BLANK_ACCOUNT_FORM, company_name: newClient.prospect.company_name, prospect_id: newClient.prospect.id,
            _prospect_uid: newClient.prospect.prospect_uid, spoc_id: newClient.prospect.owner_id ? String(newClient.prospect.owner_id) : "" }}
          onClose={() => setNewClient(null)} onChanged={() => load({ silent: true })}
          onOpenExisting={(a) => { setNewClient(null); openClient(a); }} />
      )}

      {shownProspect && (
        <Modal title={shownProspect.company_name} onClose={() => setShownProspect(null)}>
          <dl className="grid grid-cols-3 gap-x-3 gap-y-2 text-sm mb-4">
            {[["Prospect ID", shownProspect.prospect_uid], ["Date sent", fmtDate(shownProspect.assigned_at)],
              ["Sent by", userName(shownProspect.assigned_by_id)], ["RM", userName(shownProspect.owner_id)],
              ["Contact name", shownProspect.contact_name], ["Contact phone", shownProspect.contact_phone],
              ["Contact email", shownProspect.contact_email], ["Source", shownProspect.source],
              ["Services the prospect is looking for", shownProspect.notes], ["Assignor's comments", shownProspect.assignor_comments]]
              .map(([k, v]) => (<React.Fragment key={k}><dt className="text-gray-500">{k}</dt><dd className="col-span-2 text-gray-800 whitespace-pre-line">{v || "—"}</dd></React.Fragment>))}
          </dl>
          <div className="flex justify-end gap-3">
            <Button onClick={() => setShownProspect(null)}>Close</Button>
            {!readOnly && (shownProspect.owner_id === me?.id || isAdmin || canAssign) && (
              <Button variant="primary" onClick={() => createFrom(shownProspect)}>Create client</Button>
            )}
          </div>
        </Modal>
      )}

      {importPreview && (
        <ImportPreviewModal results={importPreview.results} importing={importing}
          onConfirm={confirmImport} onClose={() => setImportPreview(null)} />
      )}
    </div>
  );
}
