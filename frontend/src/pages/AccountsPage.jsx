import React, { useEffect, useRef, useState } from "react";
import { accountsApi, casesApi, usersApi, amlApi, prospectsApi } from "../api/endpoints";
import { Badge, Button, EmptyState, ErrorBanner, FilterBar, Icon, Modal, PageHeader, SearchInput, Select, Spinner } from "../components/ui";
import AccountCard from "../components/accounts/AccountCard";
import AccountFormModal from "../components/accounts/AccountFormModal";
import BulkActionBar from "../components/accounts/BulkActionBar";
import ImportPreviewModal from "../components/accounts/ImportPreviewModal";
import ClientProfilePage from "./ClientProfilePage";
import { BLANK_ACCOUNT_FORM, accountToForm } from "../components/accounts/accountForm";
import { buildAccountsCsv, parseImportRows } from "../components/accounts/accountCsv";
import { toast } from "../store/toast";
import { fmt, fmtDate, exportFilename } from "../utils/constants";
import { useAuthStore } from "../store/auth";

const BLANK_BULK = { spoc_id: "", risk_rating: "", kyc_status: "" };
const STATUSES = ["New", "WIP", "Awaiting Approval", "Approved", "Active", "Inactive", "Marked for Exit", "Exited"];
const VIEW_KEY = "triam.clients.view";

const readView = () => { try { return localStorage.getItem(VIEW_KEY) || "table"; } catch { return "table"; } };

export default function AccountsPage({ initialAccountId, initialOpenForm, initialProspectId, onNavigate } = {}) {
  const appliedInitialRef = useRef(false);
  const [accounts, setAccounts] = useState([]);
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [view, setView] = useState(readView);
  const [open, setOpen] = useState(null); // { id, tab } — the client page being shown
  const [newClient, setNewClient] = useState(null); // { key, prospect } while the New Client flow is open
  // "Create client" on a prospect lands here with the prospect chosen.
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
      const [accRes, caseRes, usersRes, countriesRes] = await Promise.all([
        accountsApi.list({ limit: 200 }), casesApi.list({ limit: 500 }), usersApi.list(), amlApi.countryRisk().catch(() => []),
      ]);
      setAccounts(accRes.items || []);
      setCases(caseRes.items || []);
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
      <ClientProfilePage key={open.id} accountId={open.id} initialTab={open.tab} users={users} countries={countries} cases={cases}
        onBack={() => { setOpen(null); load({ silent: true }); }} onChanged={() => load({ silent: true })}
        onOpenCase={(caseId) => onNavigate?.({ page: "cases", caseId })} />
    );
  }

  // Matches legal name, Unique Search Name (BRD §3) or Client ID (BRD §19).
  const q = search.toLowerCase();
  const filtered = accounts.filter((a) => (!q || [a.company_name, a.search_name, a.client_id, a.temp_id, a.account_uid].some((v) => (v || "").toLowerCase().includes(q)))
    && (!statusFilter || (a.profile_status || "New") === statusFilter)
    && (!riskFilter || a.risk_rating === riskFilter));
  const ids = filtered.map((a) => a.id);
  const openClient = (a) => setOpen({ id: a.id, tab: "overview" });

  return (
    <div className="space-y-4">
      <PageHeader title="Clients"
        subtitle={`${accounts.length} client${accounts.length === 1 ? "" : "s"} · ${fmt(accounts.reduce((s, a) => s + Number(a.total_invoiced_amount || 0), 0))} invoiced`}
        actions={<>
          <Button onClick={exportCSV}>Export CSV</Button>
          {isAdmin && (
            <>
              <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ""; }} />
              <Button onClick={() => fileInputRef.current?.click()} disabled={importing}>{importing ? "Reading…" : "Import CSV"}</Button>
            </>
          )}
          <Button variant="primary" onClick={() => setNewClient({})}><Icon name="plus" size={15} /> New Client</Button>
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
          text={accounts.length === 0 ? "Add your first client to get started." : "Try a different search or clear the filters."}
          action={accounts.length === 0 && <Button variant="primary" onClick={() => setNewClient({})}>New Client</Button>} />
      ) : view === "table" ? (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                <th className="py-2.5 px-3 w-8">
                  <input type="checkbox" checked={ids.every((id) => selectedIds.has(id))} onChange={() => toggleSelectAll(ids)} />
                </th>
                {["Client ID", "Client", "Status", "Risk", "Anchor RM", "PEP", "Next AML review", "Cases"].map((h) => (
                  <th key={h} className={`py-2.5 px-3 font-semibold ${h === "Cases" ? "text-right" : "text-left"}`}>{h}</th>
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
                    <div className="text-xs text-gray-400">{a.account_type === "Individual" ? "Individual" : (a.industry || "Corporate")}{a.is_pep ? " · PEP" : ""}</div>
                  </td>
                  <td className="py-2.5 px-3"><Badge text={a.profile_status || "New"} /></td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{a.risk_rating || "—"}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{userName(a.spoc_id)}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{a.is_pep ? "PEP" : "—"}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600">{fmtDate(a.next_aml_review_date) || "—"}</td>
                  <td className="py-2.5 px-3 text-xs text-gray-600 text-right">{a.total_cases || 0}</td>
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

      {newClient && !newClient.prospect && (
        <ProspectPicker isAdmin={isAdmin} onClose={() => setNewClient(null)}
          onPick={(p) => setNewClient({ key: Date.now(), prospect: p })}
          onGoToProspects={() => { setNewClient(null); onNavigate?.({ page: "prospects" }); }} />
      )}
      {newClient && newClient.prospect && (
        <AccountFormModal key={newClient.key} users={users} countries={countries}
          initialForm={newClient.prospect === "none" ? BLANK_ACCOUNT_FORM
            : { ...BLANK_ACCOUNT_FORM, company_name: newClient.prospect.company_name, prospect_id: newClient.prospect.id,
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




/** Triam BRD mark-up §4A — every new client is created from an assigned prospect. */
function ProspectPicker({ isAdmin, onPick, onClose, onGoToProspects }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    prospectsApi.list().then((ps) => setItems(ps.filter((p) => p.owner_id && !p.converted_account_id && p.status !== "Lost")))
      .catch(() => setItems([]));
  }, []);
  return (
    <Modal title="New client — choose the prospect" onClose={onClose}>
      <p className="text-xs text-gray-500 mb-3">Every new client starts as a prospect assigned to an RM. Choose the prospect this client is for.</p>
      {items === null ? <Spinner /> : items.length === 0 ? (
        <div className="text-sm text-gray-500 text-center py-6">
          No assigned prospects are waiting for a client.
          <div className="mt-2"><Button onClick={onGoToProspects}>Go to Prospects</Button></div>
        </div>
      ) : (
        <div className="space-y-1.5 max-h-80 overflow-y-auto">
          {items.map((p) => (
            <button key={p.id} type="button" onClick={() => onPick(p)}
              className="w-full text-left px-3 py-2 rounded-lg border border-gray-100 hover:border-brand-300 hover:bg-brand-50/40">
              <div className="text-sm font-medium text-gray-800">{p.company_name}</div>
              <div className="text-[11px] text-gray-500"><span className="font-mono">{p.prospect_uid}</span> · {p.status} · RM {p.owner_name || "—"}</div>
            </button>
          ))}
        </div>
      )}
      {isAdmin && (
        <div className="mt-3 pt-3 border-t border-gray-100 text-right">
          <button type="button" onClick={() => onPick("none")} className="text-xs text-gray-500 hover:underline">Administrator: create without a prospect</button>
        </div>
      )}
    </Modal>
  );
}
