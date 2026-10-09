import React, { useEffect, useMemo, useRef, useState } from "react";
import CaseComplianceBar, { CaseComplianceChip } from "../components/cases/CaseComplianceBar";
import CsvImportModal from "../components/CsvImportModal";
import { ROUTES, ROUTE_HELP, REGISTERED_AGENTS, routeFields, stageLabel } from "../components/cases/engagement";
import { useAuthStore } from "../store/auth";
import { casesApi, usersApi, accountsApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, MoreMenu, PageHeader, Button, SearchInput, FilterBar } from "../components/ui";
import PartyRegisterModal from "../components/PartyRegisterModal";
import CompanyDetailsModal from "../components/CompanyDetailsModal";
import LifecycleModal from "../components/LifecycleModal";
import FormationModal from "../components/FormationModal";
import ServiceSubscriptionsModal from "../components/ServiceSubscriptionsModal";
import { STAGES, STAGE_COLORS, CASE_SOURCE_OPTIONS, JURISDICTION_OPTIONS, SERVICE_TYPE_OPTIONS, CASE_STATUS_OPTIONS, CLOSED_REL_STATUSES, fmt, exportFilename } from "../utils/constants";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";

const NEXT_STAGE = STAGES.reduce((acc, s, i) => {
  if (i < STAGES.length - 1) acc[s] = STAGES[i + 1];
  return acc;
}, {});

const ENTITY_COLUMNS = [
  ["company_name", "Company Name", "Entity Name", "Name"],
  ["jurisdiction", "Jurisdiction"],
  ["incorporation_date", "Incorporation Date", "Date of Incorporation", "Inc Date"],
  ["company_number", "Company Number", "Company No", "BC Number", "Registration Number"],
  ["registered_agent", "Registered Agent", "RA"],
  ["client_id", "Client ID"],
  ["rm_email", "RM Email"],
  ["service_type", "Service"],
  ["last_renewal_date", "Last Renewal", "Last Renewal Date", "Last Annual Fee"],
  ["last_esr_date", "Last ESR", "Last ESR Date", "Last ESR Filing"],
  ["last_ar_date", "Last AR", "Last AR Date", "Last Annual Return"],
  ["notes", "Notes", "Comments"],
];

export default function CasesPage({ initialCaseId, initialStage } = {}) {
  const appliedInitialCaseRef = useRef(false);
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [importing, setImporting] = useState(false); // P6 — import existing entities
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState("kanban");
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState(initialStage || "All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [invoiceCase, setInvoiceCase] = useState(null);
  const [invoiceAmount, setInvoiceAmount] = useState("");
  const [registerCase, setRegisterCase] = useState(null);
  const [detailsCase, setDetailsCase] = useState(null);
  const [lifecycleCase, setLifecycleCase] = useState(null);
  const [formationCase, setFormationCase] = useState(null);
  const [servicesCase, setServicesCase] = useState(null);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkValues, setBulkValues] = useState({ rm_id: "", status: "" });
  const [bulkApplying, setBulkApplying] = useState(false);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [res, usersRes, accountsRes] = await Promise.all([
        casesApi.list({ limit: 500 }),
        usersApi.list(),
        accountsApi.list({ limit: 200 }),
      ]);
      setCases(res.items || []);
      setUsers(usersRes || []);
      setAccounts(accountsRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load cases");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!appliedInitialCaseRef.current && initialCaseId) {
      const match = cases.find((c) => c.id === initialCaseId);
      if (match) {
        setDetailsCase(match);
        appliedInitialCaseRef.current = true;
      }
    }
  }, [initialCaseId, cases]);

  const filtered = useMemo(() => cases.filter((c) => {
    const matchSearch = search === "" || [c.company_name, c.case_uid].some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    const matchStage = stageFilter === "All" || c.stage === stageFilter;
    const isClosed = CLOSED_REL_STATUSES.includes(c.status);
    let matchStatus;
    if (statusFilter === "All") matchStatus = !isClosed;          // exited entities hidden by default
    else if (statusFilter === "Closed RELs") matchStatus = isClosed;
    else matchStatus = c.status === statusFilter;
    return matchSearch && matchStage && matchStatus;
  }), [cases, search, stageFilter, statusFilter]);

  const openNew = () => {
    setForm({ company_name: "", source: "Other", introducer: "", onboarding_date: "", jurisdiction: "BVI", service_type: "Company Formation", account_id: null, rm_id: null, tags: "", notes: "",
      engagement_route: "Formation", previous_agent: "", incorporation_date: "", company_number: "", registered_agent: "",
      last_renewal_date: "", last_esr_date: "", last_ar_date: "" });
    setModal("new");
  };

  // Approved cases change only through Compliance: the edit is sent for approval, not applied.
  const sentToCompliance = (c) => c?.compliance_status === "Approved"
    && toast.success("Change sent to Compliance — the case updates once a CO / MLRO approves it.");

  const save = async () => {
    try {
      const clean = (o) => ({ ...o, onboarding_date: o.onboarding_date || null, introducer: o.introducer || null });
      if (modal === "new") {
        const { engagement_route, previous_agent, incorporation_date, company_number, registered_agent,
          last_renewal_date, last_esr_date, last_ar_date, ...base } = form;
        await casesApi.create({ ...clean(base), ...routeFields(form) });
        toast.success("Case created and sent to Compliance for approval.");
      } else {
        const { id, case_uid, stage, status, invoice_status, invoice_raised_date, invoice_paid_date, created_at, updated_at, compliance_status,
          engagement_route, previous_agent, prior_filing_dates, ...patch } = form;
        await casesApi.update(form.id, clean(patch));
        sentToCompliance(form);
      }
      setModal(null); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const advance = async (c) => {
    if (c.stage === "CDD Approved") {
      setInvoiceAmount("");
      setInvoiceCase(c);
      return;
    }
    try {
      if (c.stage === "Invoice Raised") await casesApi.markInvoicePaid(c.id);
      else await casesApi.changeStage(c.id, NEXT_STAGE[c.stage]);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Stage change failed");
    }
  };

  const confirmRaiseInvoice = async () => {
    const amount = parseFloat(invoiceAmount) || 0;
    try {
      await casesApi.raiseInvoice(invoiceCase.id, amount);
      setInvoiceCase(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to raise invoice");
    }
  };

  const setStatus = async (c, status) => {
    try { await casesApi.update(c.id, { status }); sentToCompliance(c); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (id) => {
    if (!(await confirmDialog("Delete this case?"))) return;
    try { await casesApi.delete(id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
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
      const results = await casesApi.bulkUpdate({ ids: [...selectedIds], [field]: field === "rm_id" ? +value : value });
      const failed = results.filter((r) => r.status === "error");
      toast[failed.length === 0 ? "success" : "error"](failed.length === 0
        ? `Updated ${results.length} case${results.length !== 1 ? "s" : ""}.`
        : `Updated ${results.length - failed.length}/${results.length}. ${failed.length} failed (e.g. access denied).`);
      setSelectedIds(new Set());
      setBulkValues({ rm_id: "", status: "" });
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Bulk update failed");
    } finally {
      setBulkApplying(false);
    }
  };

  const exportCSV = () => {
    const headers = ["UID", "Company", "Introduced By", "Onboarding Date", "Stage", "Status", "Invoice", "Source"];
    const rows = filtered.map((c) => [c.case_uid, c.company_name, c.introducer, c.onboarding_date, c.stage, c.status, c.invoice_status, c.source]);
    const csv = [headers, ...rows].map((r) => r.map((v) => `"${v ?? ""}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = exportFilename("cases"); a.click();
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const actionLabel = (stage, route) => {
    if (stage === "CDD Approved") return "Raise Invoice";
    if (stage === "Invoice Raised") return "Mark Paid";
    if (stage === "Active") return null;
    return `→ ${stageLabel(NEXT_STAGE[stage], route)}`;
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Cases"
        subtitle={<>{filtered.length} onboarding cases</>}
        actions={<>
<div className="flex gap-2 flex-wrap">
          <div className="flex border border-gray-200 rounded-lg overflow-hidden">
            <button onClick={() => setView("kanban")} className={`px-3 py-2 text-sm flex items-center gap-1.5 ${view === "kanban" ? "bg-gray-100 text-gray-800" : "text-gray-500 hover:bg-gray-50"}`}>
              <Icon name="kanban" size={14} /> Kanban
            </button>
            <button onClick={() => setView("table")} className={`px-3 py-2 text-sm flex items-center gap-1.5 ${view === "table" ? "bg-gray-100 text-gray-800" : "text-gray-500 hover:bg-gray-50"}`}>
              <Icon name="table" size={14} /> Table
            </button>
          </div>
          <button onClick={exportCSV} className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700 bg-white font-medium">Export CSV</button>
          {isAdmin && (
            <button onClick={() => setImporting(true)} className="px-3 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700 bg-white font-medium">Import existing entities</button>
          )}
          <button onClick={openNew} className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 hover:opacity-90" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={14} /> New Case
          </button>
        </div>
        </>} />

      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search cases..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-brand-400" />
        </div>
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          {["All", ...STAGES].map((s) => <option key={s} value={s}>{s === "All" ? "All stages" : s}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          {["All", "Closed RELs", ...CASE_STATUS_OPTIONS].map((s) => <option key={s} value={s}>{s === "All" ? "All open statuses" : s}</option>)}
        </select>
      </div>

      {view === "table" && selectedIds.size > 0 && (
        <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3 flex items-center flex-wrap gap-3">
          <span className="text-xs font-medium text-brand-700">{selectedIds.size} selected</span>
          <div className="flex items-center gap-1.5">
            <select value={bulkValues.rm_id} onChange={(e) => setBulkValues((p) => ({ ...p, rm_id: e.target.value }))}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none">
              <option value="">Relationship Manager…</option>
              {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
            <button disabled={!bulkValues.rm_id || bulkApplying} onClick={() => applyBulkField("rm_id")}
              className="px-2.5 py-1.5 text-xs border border-brand-300 rounded-lg bg-white hover:bg-brand-100 disabled:opacity-40">Apply</button>
          </div>
          <div className="flex items-center gap-1.5">
            <select value={bulkValues.status} onChange={(e) => setBulkValues((p) => ({ ...p, status: e.target.value }))}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none">
              <option value="">Status…</option>
              {CASE_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <button disabled={!bulkValues.status || bulkApplying} onClick={() => applyBulkField("status")}
              className="px-2.5 py-1.5 text-xs border border-brand-300 rounded-lg bg-white hover:bg-brand-100 disabled:opacity-40">Apply</button>
          </div>
          <button onClick={() => setSelectedIds(new Set())} className="text-xs text-brand-500 hover:underline ml-auto">Clear selection</button>
        </div>
      )}

      {view === "kanban" ? (
        <div className="flex gap-3 overflow-x-auto pb-4">
          {STAGES.map((stage) => {
            const stageCases = filtered.filter((c) => c.stage === stage);
            return (
              <div key={stage} className="flex-shrink-0 w-64">
                <div className="flex items-center justify-between mb-2 px-1">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ background: STAGE_COLORS[stage] }} />
                    <span className="text-xs font-semibold text-gray-700">{stage}</span>
                  </div>
                  <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">{stageCases.length}</span>
                </div>
                <div className="space-y-2 min-h-16">
                  {stageCases.map((c) => (
                    <div key={c.id}
                      className="bg-white border border-gray-100 rounded-xl p-3 shadow-sm cursor-pointer hover:shadow-md transition-shadow"
                      onClick={() => { setForm(c); setModal("edit"); }}>
                      <div className="font-semibold text-xs text-gray-800 mb-1">{c.company_name}</div>
                      <div className="text-xs text-gray-400 mb-1">{c.case_uid}
                        {c.engagement_route && c.engagement_route !== "Formation" && <span className="ml-1.5 px-1.5 py-0.5 rounded bg-violet-50 text-violet-700 text-[10px] font-semibold">{c.engagement_route}</span>}
                      </div>
                      {c.engagement_route === "Transfer In" && ["Application Submitted", "License Received"].includes(c.stage) && (
                        <div className="text-[11px] text-violet-700 mb-1">{stageLabel(c.stage, c.engagement_route)}</div>
                      )}
                      {(c.jurisdiction || c.service_type) && (
                        <div className="text-xs text-gray-400 mb-2">{[c.jurisdiction, c.service_type].filter(Boolean).join(" · ")}</div>
                      )}
                      <div className="flex items-center gap-1 flex-wrap">
                        <CaseComplianceChip status={c.compliance_status} />
                        {c.status !== "Active" && <Badge text={c.status} />}
                        {c.invoice_status && c.invoice_status !== "Not Raised" && <Badge text={`Invoice ${c.invoice_status}`} />}
                      </div>
                      <div className="mt-2 pt-2 border-t border-gray-50 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        {actionLabel(stage, c.engagement_route) && (
                          <button onClick={() => advance(c)} disabled={c.compliance_status !== "Approved"}
                            title={c.compliance_status !== "Approved" ? "Waiting for Compliance approval" : ""}
                            className="flex-1 text-xs px-2 py-1 rounded-lg text-white font-medium disabled:opacity-40 disabled:cursor-not-allowed truncate"
                            style={{ background: "#1a3a5c" }}>
                            {actionLabel(stage, c.engagement_route)}
                          </button>
                        )}
                        <MoreMenu items={[
                          { label: "Open case", onClick: () => { setForm(c); setModal("edit"); } },
                          { label: "Register (directors, shareholders, UBOs)", onClick: () => setRegisterCase(c) },
                          { label: "Company details", onClick: () => setDetailsCase(c) },
                          { label: "Formation", onClick: () => setFormationCase(c) },
                          { label: "Lifecycle", onClick: () => setLifecycleCase(c) },
                          { label: "Services", onClick: () => setServicesCase(c) },
                          { label: "Mark docs pending", onClick: () => setStatus(c, "Docs Pending"), hidden: c.status !== "Active" },
                          { label: "Resume", onClick: () => setStatus(c, "Active"), hidden: c.status !== "Docs Pending" },
                        ]} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="py-3 px-4">
                  <input type="checkbox" checked={filtered.length > 0 && filtered.every((c) => selectedIds.has(c.id))}
                    onChange={() => toggleSelectAllFiltered(filtered.map((c) => c.id))} />
                </th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Case</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Company</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Introduced By</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Stage</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Status</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Invoice</th>
                <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Amount</th>
                <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 px-4">
                    <input type="checkbox" checked={selectedIds.has(c.id)} onChange={() => toggleSelected(c.id)} />
                  </td>
                  <td className="py-3 px-4 text-xs font-medium text-gray-800">{c.case_uid}</td>
                  <td className="py-3 px-4 text-xs text-gray-600">{c.company_name}<div><CaseComplianceChip status={c.compliance_status} /></div></td>
                  <td className="py-3 px-4 text-xs text-gray-500">{c.introducer || "—"}</td>
                  <td className="py-3 px-4"><Badge text={stageLabel(c.stage, c.engagement_route)} /></td>
                  <td className="py-3 px-4"><Badge text={c.status} /></td>
                  <td className="py-3 px-4"><Badge text={c.invoice_status} /></td>
                  <td className="py-3 px-4 text-xs text-right text-gray-600">{fmt(c.invoice_amount)}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1">
                      <button onClick={() => setRegisterCase(c)}
                        className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600" title="Directors, Shareholders & UBOs">
                        <Icon name="accounts" size={14} />
                      </button>
                      <button onClick={() => setDetailsCase(c)}
                        className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600" title="Company Details">
                        <Icon name="compliance" size={14} />
                      </button>
                      <button onClick={() => setFormationCase(c)}
                        className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600" title="Formation — screening / MLRO / Vistra loop">
                        <Icon name="cdd" size={14} />
                      </button>
                      <button onClick={() => setLifecycleCase(c)}
                        className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600" title="Entity Lifecycle — closure / restoration / transfer">
                        <Icon name="activities" size={14} />
                      </button>
                      <button onClick={() => setServicesCase(c)}
                        className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600" title="Service Subscriptions">
                        <Icon name="invoices" size={14} />
                      </button>
                      <button onClick={() => { setForm(c); setModal("edit"); }}
                        className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600">
                        <Icon name="edit" size={14} />
                      </button>
                      <button onClick={() => remove(c.id)}
                        className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                        <Icon name="del" size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {invoiceCase && (
        <Modal title={`Raise Invoice — ${invoiceCase.company_name}`} onClose={() => setInvoiceCase(null)}>
          <p className="text-sm text-gray-600 mb-4">Enter the invoice amount before raising. This will move the case to <strong>Invoice Raised</strong>.</p>
          <Field label="Invoice Amount (AED)">
            <Input
              type="number"
              min="0"
              step="0.01"
              value={invoiceAmount}
              onChange={(e) => setInvoiceAmount(e.target.value)}
              placeholder="e.g. 15000"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && confirmRaiseInvoice()}
            />
          </Field>
          <div className="flex justify-end gap-3 mt-5">
            <button onClick={() => setInvoiceCase(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={confirmRaiseInvoice} className="px-4 py-2 text-sm text-white rounded-lg font-medium" style={{ background: "#1a3a5c" }}>
              Raise Invoice
            </button>
          </div>
        </Modal>
      )}

      {registerCase && (
        <PartyRegisterModal caseItem={registerCase} onClose={() => setRegisterCase(null)} />
      )}

      {importing && (
        <CsvImportModal title="Import existing entities" columns={ENTITY_COLUMNS} required={["company_name", "jurisdiction", "incorporation_date"]}
          templateName="existing-entities-template.csv" onRun={casesApi.importEntities} onClose={() => setImporting(false)} onDone={load} />
      )}

      {detailsCase && (
        <CompanyDetailsModal caseItem={detailsCase} onClose={() => setDetailsCase(null)} />
      )}

      {lifecycleCase && (
        <LifecycleModal caseItem={lifecycleCase} onClose={(changed) => { setLifecycleCase(null); if (changed) load(); }} />
      )}

      {formationCase && (
        <FormationModal caseItem={formationCase} users={users} onClose={(changed) => { setFormationCase(null); if (changed) load(); }} />
      )}

      {servicesCase && (
        <ServiceSubscriptionsModal caseItem={servicesCase} onClose={() => setServicesCase(null)} />
      )}

      {modal && (
        <Modal title={modal === "new" ? "New Case" : `Edit ${form.case_uid}`} onClose={() => setModal(null)}>
          {modal === "edit" && <CaseComplianceBar caseId={form.id} onChanged={() => { setModal(null); load(); }} />}
          {modal === "new" && <p className="text-xs text-gray-500 mb-3">A new case is sent to Compliance for approval before it can move through the pipeline.</p>}
          {modal === "new" && (
            <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 mb-3">
              <Field label="Engagement route" required>
                <div className="flex flex-wrap gap-1.5">
                  {ROUTES.map((r) => (
                    <button key={r} type="button" onClick={() => setForm((p) => ({ ...p, engagement_route: r }))}
                      className={`px-3 py-1.5 text-xs rounded-lg border ${form.engagement_route === r ? "text-white border-transparent" : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"}`}
                      style={form.engagement_route === r ? { background: "#1a3a5c" } : {}}>{r}</button>
                  ))}
                </div>
              </Field>
              <p className="text-[11px] text-gray-500 -mt-2">{ROUTE_HELP[form.engagement_route || "Formation"]}</p>
              {form.engagement_route && form.engagement_route !== "Formation" && (
                <div className="grid grid-cols-2 gap-x-4 mt-3">
                  {form.engagement_route === "Transfer In" && (
                    <Field label="Previous registered agent" required>
                      <Input value={form.previous_agent || ""} onChange={(e) => setForm((p) => ({ ...p, previous_agent: e.target.value }))} placeholder="Agent the company is leaving" />
                    </Field>
                  )}
                  <Field label="Incorporation date" required>
                    <Input type="date" value={form.incorporation_date || ""} onChange={(e) => setForm((p) => ({ ...p, incorporation_date: e.target.value }))} />
                  </Field>
                  <Field label="Company number">
                    <Input value={form.company_number || ""} onChange={(e) => setForm((p) => ({ ...p, company_number: e.target.value }))} />
                  </Field>
                  <Field label="Registered agent">
                    <Select value={form.registered_agent || ""} onChange={(e) => setForm((p) => ({ ...p, registered_agent: e.target.value }))}>
                      <option value="">—</option>
                      {REGISTERED_AGENTS.map((a) => <option key={a}>{a}</option>)}
                    </Select>
                  </Field>
                  <Field label="Last licence renewal"><Input type="date" value={form.last_renewal_date || ""} onChange={(e) => setForm((p) => ({ ...p, last_renewal_date: e.target.value }))} /></Field>
                  <Field label="Last ESR filing"><Input type="date" value={form.last_esr_date || ""} onChange={(e) => setForm((p) => ({ ...p, last_esr_date: e.target.value }))} /></Field>
                  <Field label="Last Annual Return"><Input type="date" value={form.last_ar_date || ""} onChange={(e) => setForm((p) => ({ ...p, last_ar_date: e.target.value }))} /></Field>
                  <p className="col-span-2 text-[11px] text-gray-500 -mt-2">The Filing Calendar uses these dates; anything already overdue is flagged.</p>
                </div>
              )}
            </div>
          )}
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Client">
              <Select value={form.account_id || ""} onChange={(e) => {
                const id = e.target.value ? +e.target.value : null;
                const picked = accounts.find((a) => a.id === id);
                setForm((p) => ({ ...p, account_id: id, company_name: picked ? picked.company_name : "", tags: picked ? (picked.tags || "") : p.tags }));
              }}>
                <option value="">— New / not yet a client —</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Company Name" required>
              {form.account_id ? (
                <Input value={form.company_name || ""} readOnly disabled className="bg-gray-50 text-gray-500" />
              ) : (
                <Input value={form.company_name || ""} onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))} placeholder="Type a name, or pick an existing Client above" />
              )}
            </Field>
            <Field label="Source">
              <Select value={form.source || "Other"} onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))}>
                {CASE_SOURCE_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Introduced By"><Input value={form.introducer || ""} onChange={(e) => setForm((p) => ({ ...p, introducer: e.target.value }))} placeholder="e.g. Vistra, Rosemont, a referrer" /></Field>
            <Field label="Onboarding Date"><Input type="date" value={form.onboarding_date || ""} onChange={(e) => setForm((p) => ({ ...p, onboarding_date: e.target.value }))} /></Field>
            <Field label="Jurisdiction">
              <Select value={form.jurisdiction || ""} onChange={(e) => setForm((p) => ({ ...p, jurisdiction: e.target.value }))}>
                <option value="">— Select —</option>
                {JURISDICTION_OPTIONS.map((j) => <option key={j}>{j}</option>)}
              </Select>
            </Field>
            <Field label="Service Type">
              <Select value={form.service_type || ""} onChange={(e) => setForm((p) => ({ ...p, service_type: e.target.value }))}>
                <option value="">— Select —</option>
                {SERVICE_TYPE_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Relationship Manager">
              <Select value={form.rm_id || ""} onChange={(e) => setForm((p) => ({ ...p, rm_id: e.target.value ? +e.target.value : null }))}>
                <option value="">— Auto-assign (least loaded RM) —</option>
                {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            {modal === "edit" && (
              <Field label="Additional RMs">
                <AdditionalRMsEditor
                  caseId={form.id}
                  rmIds={form.additional_rm_ids || []}
                  primaryRmId={form.rm_id}
                  users={users}
                  onChange={(ids) => setForm((p) => ({ ...p, additional_rm_ids: ids }))}
                />
              </Field>
            )}
            <Field label="Ops Owner">
              <Select value={form.ops_owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, ops_owner_id: e.target.value ? +e.target.value : null }))}>
                <option value="">— Unassigned —</option>
                {users.filter((u) => u.role === "ops").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            <Field label="Tags"><Input value={form.tags || ""} onChange={(e) => setForm((p) => ({ ...p, tags: e.target.value }))} placeholder="Auto-filled from the selected Client — editable" /></Field>
          </div>
          <Field label="Notes"><Textarea value={form.notes || ""} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function AdditionalRMsEditor({ caseId, rmIds, primaryRmId, users, onChange }) {
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const rmUsers = users.filter((u) => u.role === "rm");
  const byId = (id) => rmUsers.find((u) => u.id === id);
  const available = rmUsers.filter((u) => u.id !== primaryRmId && !rmIds.includes(u.id));

  const add = async (userId) => {
    if (!userId) return;
    setBusy(true);
    try {
      const updated = await casesApi.addRM(caseId, +userId);
      onChange(updated.additional_rm_ids || []);
      setAdding(false);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add RM");
    } finally { setBusy(false); }
  };

  const remove = async (userId) => {
    setBusy(true);
    try {
      const updated = await casesApi.removeRM(caseId, userId);
      onChange(updated.additional_rm_ids || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to remove RM");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-1.5">
        {rmIds.length === 0 && !adding && <span className="text-xs text-gray-400">None</span>}
        {rmIds.map((id) => (
          <span key={id} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700">
            {byId(id)?.name || `User #${id}`}
            <button type="button" disabled={busy} onClick={() => remove(id)} className="text-gray-400 hover:text-red-500">✕</button>
          </span>
        ))}
      </div>
      {adding ? (
        <div className="flex gap-1">
          <Select autoFocus disabled={busy} onChange={(e) => add(e.target.value)} defaultValue="">
            <option value="">— select RM —</option>
            {available.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </Select>
          <button type="button" onClick={() => setAdding(false)} className="px-2 text-xs text-gray-400 hover:text-red-500">✕</button>
        </div>
      ) : (
        <button type="button" onClick={() => setAdding(true)} disabled={busy || available.length === 0}
          className="text-xs px-2 py-0.5 border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-50">＋ Add RM</button>
      )}
    </div>
  );
}
