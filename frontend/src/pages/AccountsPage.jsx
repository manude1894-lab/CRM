import React, { useEffect, useRef, useState } from "react";
import { accountsApi, usersApi, countriesApi, prospectsApi } from "../api/endpoints";
import { Badge, Button, EmptyState, ErrorBanner, FilterBar, Icon, PageHeader, SearchInput, Select, Spinner } from "../components/ui";
import AccountCard from "../components/accounts/AccountCard";
import AccountFormModal from "../components/accounts/AccountFormModal";
import BulkActionBar from "../components/accounts/BulkActionBar";
import ImportPreviewModal from "../components/accounts/ImportPreviewModal";
import ClientProfilePage from "./ClientProfilePage";
import { BLANK_ACCOUNT_FORM } from "../components/accounts/accountForm";
import { buildAccountsCsv, parseImportRows } from "../components/accounts/accountCsv";
import { toast } from "../store/toast";
import { fmtDate, exportFilename } from "../utils/constants";
import { useAuthStore } from "../store/auth";

const BLANK_BULK = { spoc_id: "", risk_rating: "" };
const STATUSES = ["New", "WIP", "Awaiting Approval", "Approved", "Active", "Inactive", "Marked for Exit", "Exited"];
const VIEW_KEY = "triam.clients.view";

const readView = () => { try { return localStorage.getItem(VIEW_KEY) || "table"; } catch { return "table"; } };

export default function AccountsPage({ initialAccountId, initialOpenForm, initialProspectId, onNavigate } = {}) {
  const appliedInitialRef = useRef(false);
  const [accounts, setAccounts] = useState([]);
  const [users, setUsers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
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

  // `silent` refreshes in the background without the full-page spinner.
  const load = async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const [accRes, usersRes, countriesRes] = await Promise.all([
        accountsApi.list({ limit: 200 }), usersApi.list(), countriesApi.list().catch(() => []),
      ]);
      setAccounts(accRes.items || []);
      setUsers(usersRes || []);
      setCountries(countriesRes || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load clients");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  // Arriving from elsewhere (e.g. "Review" in the Compliance inbox) opens that client's page.
  useEffect(() => {
    if (!appliedInitialRef.current && initialAccountId && accounts.some((a) => a.id === initialAccountId)) {
      setOpen({ id: initialAccountId, tab: initialOpenForm ? "profile" : "overview" });
      appliedInitialRef.current = true;
    }
  }, [initialAccountId, accounts]);

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

  const exportCSV = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([buildAccountsCsv(accounts, users)], { type: "text/csv" }));
    a.download = exportFilename("clients"); a.click();
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
      <ClientProfilePage key={open.id} accountId={open.id} initialTab={open.tab} users={users} countries={countries}
        onBack={() => { setOpen(null); load({ silent: true }); }} onChanged={() => load({ silent: true })} />
    );
  }

  // Matches legal name, Unique Search Name (BRD §3) or Client ID (BRD §18).
  const q = search.toLowerCase();
  const filtered = accounts.filter((a) => (!q || [a.company_name, a.search_name, a.client_id, a.temp_id, a.account_uid].some((v) => (v || "").toLowerCase().includes(q)))
    && (!statusFilter || (a.profile_status || "New") === statusFilter)
    && (!riskFilter || a.risk_rating === riskFilter));
  const ids = filtered.map((a) => a.id);
  const openClient = (a) => setOpen({ id: a.id, tab: "overview" });

  return (
    <div className="space-y-4">
      <PageHeader title="Clients"
        subtitle={`${accounts.length} client${accounts.length === 1 ? "" : "s"} · new clients are created from an assigned prospect`}
        actions={<>
          <Button onClick={exportCSV}>Export CSV</Button>
          {isAdmin && (
            <>
              <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ""; }} />
              <Button onClick={() => fileInputRef.current?.click()} disabled={importing}>{importing ? "Reading…" : "Import CSV"}</Button>
            </>
          )}
          <Button variant="primary" onClick={() => onNavigate?.({ page: "prospects" })}>Go to Prospects</Button>
        </>}
      />

      <FilterBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search by name, search name or Client ID…" />
        <div className="w-44"><Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s}>{s}</option>)}
        </Select></div>
        <div className="w-40"><Select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
          <option value="">All risk levels</option>
          {["High", "Medium", "Low"].map((r) => <option key={r} value={r}>{r} risk</option>)}
        </Select></div>
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
          title={accounts.length === 0 ? "No clients yet" : "No clients match these filters"}
          text={accounts.length === 0 ? "Clients are created from a prospect: assign it to an RM, then choose Create client." : "Try a different search or clear the filters."}
          action={accounts.length === 0 && <Button variant="primary" onClick={() => onNavigate?.({ page: "prospects" })}>Go to Prospects</Button>} />
      ) : view === "table" ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                <th className="py-2.5 px-3 w-8">
                  <input type="checkbox" checked={ids.every((id) => selectedIds.has(id))} onChange={() => toggleSelectAll(ids)} />
                </th>
                {["Client ID", "Client", "Status", "Risk", "Anchor RM", "PEP", "Next AML review"].map((h) => (
                  <th key={h} className="py-2.5 px-3 font-semibold text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.id} onClick={() => openClient(a)} className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer">
                  <td className="py-2.5 px-3" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(a.id)} onChange={() => toggleSelected(a.id)} />
                  </td>
                  <td className="py-2.5 px-3 font-mono text-xs text-gray-600">{a.client_id || <span className="text-gray-400" title="Temporary ID until Compliance approves">{a.temp_id || a.account_uid}</span>}</td>
                  <td className="py-2.5 px-3">
                    <div className="font-medium text-gray-800">{a.company_name}</div>
                    <div className="text-xs text-gray-400">{a.account_type === "Individual" ? "Individual" : [a.client_category, a.country].filter(Boolean).join(" · ") || "Corporate"}{a.is_pep ? " · PEP" : ""}</div>
                  </td>
                  <td className="py-2.5 px-3"><Badge text={a.profile_status || "New"} /></td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{a.risk_rating || "—"}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{userName(a.spoc_id)}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{a.is_pep ? "PEP" : "—"}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{fmtDate(a.next_aml_review_date) || "—"}</td>
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

      {newClient && (
        <AccountFormModal key={newClient.key} users={users} countries={countries}
          initialForm={{ ...BLANK_ACCOUNT_FORM, company_name: newClient.prospect.company_name, prospect_id: newClient.prospect.id,
            _prospect_uid: newClient.prospect.prospect_uid, spoc_id: newClient.prospect.owner_id ? String(newClient.prospect.owner_id) : "" }}
          onClose={() => setNewClient(null)} onChanged={() => load({ silent: true })}
          onOpenExisting={(a) => { setNewClient(null); openClient(a); }} />
      )}

      {importPreview && (
        <ImportPreviewModal results={importPreview.results} importing={importing}
          onConfirm={confirmImport} onClose={() => setImportPreview(null)} />
      )}
    </div>
  );
}
