import React, { useEffect, useRef, useState } from "react";
import { accountsApi, casesApi, usersApi, amlApi } from "../api/endpoints";
import { Icon, Modal, Spinner, ErrorBanner } from "../components/ui";
import AccountPartyModal from "../components/AccountPartyModal";
import TrackRecordModal from "../components/TrackRecordModal";
import ClientDocumentsFolder from "../components/accounts/ClientDocumentsFolder";
import AccountCard from "../components/accounts/AccountCard";
import AccountFormModal from "../components/accounts/AccountFormModal";
import BulkActionBar from "../components/accounts/BulkActionBar";
import ImportPreviewModal from "../components/accounts/ImportPreviewModal";
import AccountHistoryModal from "../components/accounts/AccountHistoryModal";
import ClientServicingModal from "../components/accounts/ClientServicingModal";
import { BLANK_ACCOUNT_FORM, accountToForm } from "../components/accounts/accountForm";
import { buildAccountsCsv, parseImportRows } from "../components/accounts/accountCsv";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";
import { fmt, exportFilename } from "../utils/constants";
import { useAuthStore } from "../store/auth";

const BLANK_BULK = { spoc_id: "", risk_rating: "", kyc_status: "" };

export default function AccountsPage({ initialAccountId, initialOpenForm } = {}) {
  const appliedInitialRef = useRef(false);
  const [accounts, setAccounts] = useState([]);
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  // { form, key } while the New/Edit modal is open; key remounts the modal when switching client.
  const [formModal, setFormModal] = useState(null);
  const [importPreview, setImportPreview] = useState(null); // { rows, results, created, skipped }
  const [importing, setImporting] = useState(false);
  const [partiesAccount, setPartiesAccount] = useState(null); // Account being edited in AccountPartyModal
  const [trackRecordAccount, setTrackRecordAccount] = useState(null); // Account being viewed in TrackRecordModal
  const [attachmentsAccount, setAttachmentsAccount] = useState(null); // Account whose Attachments modal is open
  const [historyAccount, setHistoryAccount] = useState(null); // Account whose audit history is open
  const [servicingAccount, setServicingAccount] = useState(null); // BRD §17 Visit/Call Reports + Service Requests
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkValues, setBulkValues] = useState(BLANK_BULK);
  const [bulkApplying, setBulkApplying] = useState(false);
  const fileInputRef = useRef(null);
  const isAdmin = useAuthStore((s) => s.isAdmin());

  // `silent` refreshes in the background without the full-page spinner, which would unmount open modals.
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

  useEffect(() => {
    const target = accounts.find((a) => a.id === initialAccountId);
    if (!appliedInitialRef.current && initialAccountId && target) {
      setSelectedId(initialAccountId);
      if (initialOpenForm) openEdit(target); // e.g. "Review" from the Approvals inbox
      appliedInitialRef.current = true;
    }
  }, [initialAccountId, accounts]);

  const openForm = (form) => setFormModal({ form, key: Date.now() });
  const openNew = () => openForm(BLANK_ACCOUNT_FORM);
  const openEdit = (a) => openForm(accountToForm(a));

  const deleteAccount = async (id) => {
    if (!(await confirmDialog("Delete this client? This cannot be undone."))) return;
    try {
      await accountsApi.delete(id);
      setSelectedId(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to delete client");
    }
  };

  const toggleSelected = (id) => setSelectedIds((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const toggleSelectAllFiltered = (ids) => setSelectedIds((prev) =>
    ids.every((id) => prev.has(id)) ? new Set() : new Set(ids)
  );

  const applyBulkField = async (field) => {
    const value = bulkValues[field];
    if (!value || selectedIds.size === 0) return;
    setBulkApplying(true);
    try {
      const results = await accountsApi.bulkUpdate({ ids: [...selectedIds], [field]: field === "spoc_id" ? +value : value });
      const failed = results.filter((r) => r.status === "error");
      toast[failed.length === 0 ? "success" : "error"](failed.length === 0
        ? `Updated ${results.length} client${results.length !== 1 ? "s" : ""}.`
        : `Updated ${results.length - failed.length}/${results.length}. ${failed.length} failed (e.g. access denied).`);
      setSelectedIds(new Set());
      setBulkValues(BLANK_BULK);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Bulk update failed");
    } finally {
      setBulkApplying(false);
    }
  };

  const exportCSV = () => {
    const csv = buildAccountsCsv(accounts, users);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
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

  // Matches legal name, Unique Search Name (BRD §3) or Client ID (BRD §19).
  const filtered = accounts.filter((a) => search === "" || [a.company_name, a.search_name, a.client_id]
    .some((v) => (v || "").toLowerCase().includes(search.toLowerCase())));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Clients</h1>
          <p className="text-sm text-gray-500">{accounts.length} clients · {fmt(accounts.reduce((s, a) => s + Number(a.total_invoiced_amount || 0), 0))} total invoiced</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={exportCSV} className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">Export CSV</button>
          {isAdmin && (
            <>
              <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); e.target.value = ""; }} />
              <button onClick={() => fileInputRef.current?.click()} disabled={importing}
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-50">
                {importing ? "Reading..." : "Import CSV"}
              </button>
            </>
          )}
          <button onClick={openNew}
            className="flex items-center gap-2 px-4 py-2 text-sm text-white rounded-lg font-medium"
            style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={15} /> New Client
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative max-w-md flex-1 min-w-[200px]">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search clients..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-brand-400" />
        </div>
        {filtered.length > 0 && (
          <label className="flex items-center gap-1.5 text-xs text-gray-500">
            <input type="checkbox" checked={filtered.every((a) => selectedIds.has(a.id))}
              onChange={() => toggleSelectAllFiltered(filtered.map((a) => a.id))} />
            Select all ({filtered.length})
          </label>
        )}
      </div>

      {selectedIds.size > 0 && (
        <BulkActionBar count={selectedIds.size} users={users} values={bulkValues} onChange={setBulkValues}
          onApply={applyBulkField} applying={bulkApplying} onClear={() => setSelectedIds(new Set())} />
      )}

      {filtered.length === 0 && (
        <div className="text-center py-16 text-gray-400 text-sm">
          No clients yet. Click <strong>New Client</strong> to add your first client company.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((a) => (
          <AccountCard key={a.id}
            account={a}
            cases={cases.filter((c) => c.account_id === a.id)}
            isOpen={selectedId === a.id}
            isSelected={selectedIds.has(a.id)}
            onToggleOpen={() => setSelectedId(selectedId === a.id ? null : a.id)}
            onToggleSelected={() => toggleSelected(a.id)}
            onEdit={() => openEdit(a)}
            onDelete={() => deleteAccount(a.id)}
            onManageParties={() => setPartiesAccount(a)}
            onTrackRecord={() => setTrackRecordAccount(a)}
            onAttachments={() => setAttachmentsAccount(a)}
            onHistory={() => setHistoryAccount(a)}
            onServicing={() => setServicingAccount(a)} />
        ))}
      </div>

      {formModal && (
        <AccountFormModal key={formModal.key}
          initialForm={formModal.form}
          users={users}
          countries={countries}
          onClose={() => setFormModal(null)}
          onChanged={() => load({ silent: true })}
          onOpenExisting={openEdit} />
      )}

      {importPreview && (
        <ImportPreviewModal results={importPreview.results} importing={importing}
          onConfirm={confirmImport} onClose={() => setImportPreview(null)} />
      )}

      {partiesAccount && (
        <AccountPartyModal account={partiesAccount} onClose={() => { setPartiesAccount(null); load(); }} />
      )}

      {trackRecordAccount && (
        <TrackRecordModal account={trackRecordAccount} onClose={() => setTrackRecordAccount(null)} />
      )}

      {servicingAccount && (
        <ClientServicingModal account={servicingAccount} cases={cases} onClose={() => setServicingAccount(null)} />
      )}

      {historyAccount && (
        <AccountHistoryModal account={historyAccount} onClose={() => setHistoryAccount(null)} />
      )}

      {attachmentsAccount && (
        <Modal title={`Documents — ${attachmentsAccount.company_name}`} onClose={() => setAttachmentsAccount(null)}>
          <ClientDocumentsFolder accountId={attachmentsAccount.id} onboarding={["New", "WIP"].includes(attachmentsAccount.profile_status)} />
        </Modal>
      )}
    </div>
  );
}
