import React, { useEffect, useRef, useState } from "react";
import { accountsApi, usersApi, countriesApi, prospectsApi } from "../api/endpoints";
import { Badge, Button, EmptyState, ErrorBanner, FilterBar, Icon, Modal, PageHeader, SearchInput, Select, Spinner } from "../components/ui";
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
// Triam input 19-10-2026: clients being onboarded and existing clients are separate menu items.
const SCOPES = {
  onboarding: {
    title: "New Client Onboarding", statuses: ["New", "WIP", "Awaiting Approval"],
    subtitle: (n) => `${n} client${n === 1 ? "" : "s"} being onboarded`,
    empty: "Clients appear here once they are created from a prospect sent to the RM.",
  },
  maintenance: {
    title: "Client Data Maintenance", statuses: ["Approved", "Active", "Inactive", "Marked for Exit", "Exited"],
    subtitle: (n) => `${n} existing client${n === 1 ? "" : "s"} · changes go to Compliance for approval (BRD §11)`,
    empty: "Clients appear here once the Approver has approved them, or when they are imported.",
  },
};
const VIEW_KEY = "triam.clients.view";

const readView = () => { try { return localStorage.getItem(VIEW_KEY) || "table"; } catch { return "table"; } };

export default function AccountsPage({ scope = "onboarding", initialAccountId, initialOpenForm, initialProspectId, onNavigate } = {}) {
  const cfg = SCOPES[scope];
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
  const me = useAuthStore((s) => s.user);
  const canAssign = useAuthStore((s) => s.can("prospect.assign"));
  const [prospects, setProspects] = useState([]);
  const [shownProspect, setShownProspect] = useState(null);

  // `silent` refreshes in the background without the full-page spinner.
  const load = async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      setError(null);
      const [accRes, usersRes, countriesRes, prospectRes] = await Promise.all([
        accountsApi.list({ limit: 500 }), usersApi.list(), countriesApi.list().catch(() => []),
        scope === "onboarding" ? prospectsApi.list().catch(() => []) : Promise.resolve([]),
      ]);
      setAccounts(accRes.items || []);
      setProspects(prospectRes || []);
      setUsers(usersRes || []);
      setCountries(countriesRes || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load clients");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  // Arriving from elsewhere (e.g. "Review" in the Compliance inbox) opens that client's page.
  useEffect(() => {
    const target = accounts.find((a) => a.id === initialAccountId);
    if (!appliedInitialRef.current && initialAccountId && target) {
      appliedInitialRef.current = true;
      if (!cfg.statuses.includes(target.profile_status || "New")) {
        onNavigate?.({ page: scope === "onboarding" ? "maintenance" : "accounts", accountId: target.id, openForm: initialOpenForm });
        return;
      }
      setOpen({ id: initialAccountId, tab: initialOpenForm ? "profile" : "overview" });
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
      <ClientProfilePage key={open.id} accountId={open.id} initialTab={open.tab} users={users} countries={countries} backLabel={cfg.title}
        onBack={() => { setOpen(null); load({ silent: true }); }} onChanged={() => load({ silent: true })} />
    );
  }

  // Only this menu item's clients: being onboarded, or existing (Triam input 19-10-2026).
  const scoped = accounts.filter((a) => cfg.statuses.includes(a.profile_status || "New"));
  // Matches legal name, Unique Search Name (BRD §3) or Client ID (BRD §18).
  const q = search.toLowerCase();
  const filtered = scoped.filter((a) => (!q || [a.company_name, a.search_name, a.client_id, a.temp_id, a.account_uid].some((v) => (v || "").toLowerCase().includes(q)))
    && (!statusFilter || (a.profile_status || "New") === statusFilter)
    && (!riskFilter || a.risk_rating === riskFilter));
  const ids = filtered.map((a) => a.id);
  const openClient = (a) => setOpen({ id: a.id, tab: "overview" });
  // Prospects sent to an RM and still waiting for their client: the RM sees their own, the Prospecting
  // Coordinator and administrators see all. Newest first (Triam input 19-10-2026).
  const waiting = prospects
    .filter((p) => p.owner_id && !p.converted_account_id && p.status !== "Lost" && (isAdmin || p.owner_id === me?.id || canAssign))
    .sort((x, y) => String(y.assigned_at || y.created_at).localeCompare(String(x.assigned_at || x.created_at)));
  const createFrom = (p) => { setShownProspect(null); setNewClient({ key: Date.now(), prospect: p }); };

  return (
    <div className="space-y-4">
      <PageHeader title={cfg.title} subtitle={cfg.subtitle(scoped.length)}
        actions={<>
          <Button onClick={exportCSV}>Export CSV</Button>
          {isAdmin && scope === "maintenance" && (
            <>
              <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ""; }} />
              <Button onClick={() => fileInputRef.current?.click()} disabled={importing}>{importing ? "Reading…" : "Import CSV"}</Button>
            </>
          )}
          {scope === "onboarding" && <Button variant="primary" onClick={() => onNavigate?.({ page: "prospects" })}>Go to Prospects</Button>}
        </>}
      />

      {scope === "onboarding" && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <div className="px-4 py-3 border-b border-gray-100 text-sm font-semibold text-gray-800">
            {isAdmin || canAssign ? "Prospects sent to RMs" : "Prospects sent to me"}
            <span className="ml-2 text-xs font-normal text-gray-400">{waiting.length} waiting for the client to be created</span>
          </div>
          {waiting.length === 0 ? <p className="px-4 py-5 text-sm text-gray-400">No prospects waiting.</p> : (
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
                      <div className="text-[11px] text-gray-400 font-mono">{p.prospect_uid}{isAdmin || p.owner_id !== me?.id ? ` · ${userName(p.owner_id)}` : ""}</div>
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

      <FilterBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search by name, search name or Client ID…" />
        <div className="w-44"><Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          {cfg.statuses.map((s) => <option key={s}>{s}</option>)}
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
          title={scoped.length === 0 ? `No clients in ${cfg.title}` : "No clients match these filters"}
          text={scoped.length === 0 ? cfg.empty : "Try a different search or clear the filters."} />
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
            {(shownProspect.owner_id === me?.id || isAdmin || canAssign) && (
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
