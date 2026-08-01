import React, { useEffect, useMemo, useState } from "react";
import { casesApi, usersApi, accountsApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";
import { STAGES, STAGE_COLORS, CASE_SOURCE_OPTIONS, fmt } from "../utils/constants";

const NEXT_STAGE = STAGES.reduce((acc, s, i) => {
  if (i < STAGES.length - 1) acc[s] = STAGES[i + 1];
  return acc;
}, {});

export default function CasesPage() {
  const [cases, setCases] = useState([]);
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState("kanban");
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("All");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [invoiceCase, setInvoiceCase] = useState(null);
  const [invoiceAmount, setInvoiceAmount] = useState("");

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

  const filtered = useMemo(() => cases.filter((c) => {
    const matchSearch = search === "" || [c.company_name, c.case_uid].some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    const matchStage = stageFilter === "All" || c.stage === stageFilter;
    return matchSearch && matchStage;
  }), [cases, search, stageFilter]);

  const openNew = () => {
    setForm({ company_name: "", source: "Other", account_id: null, rm_id: null, tags: "", notes: "" });
    setModal("new");
  };

  const save = async () => {
    try {
      if (modal === "new") {
        await casesApi.create(form);
      } else {
        const { id, case_uid, stage, status, invoice_status, invoice_raised_date, invoice_paid_date, created_at, updated_at, ...patch } = form;
        await casesApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
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
      alert(e.response?.data?.detail || "Stage change failed");
    }
  };

  const confirmRaiseInvoice = async () => {
    const amount = parseFloat(invoiceAmount) || 0;
    try {
      await casesApi.raiseInvoice(invoiceCase.id, amount);
      setInvoiceCase(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to raise invoice");
    }
  };

  const setStatus = async (c, status) => {
    try { await casesApi.update(c.id, { status }); load(); }
    catch (e) { alert(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (id) => {
    if (!confirm("Delete this case?")) return;
    try { await casesApi.delete(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  const exportCSV = () => {
    const headers = ["UID", "Company", "Stage", "Status", "Invoice", "Source"];
    const rows = filtered.map((c) => [c.case_uid, c.company_name, c.stage, c.status, c.invoice_status, c.source]);
    const csv = [headers, ...rows].map((r) => r.map((v) => `"${v ?? ""}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "cases.csv"; a.click();
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const actionLabel = (stage) => {
    if (stage === "CDD Approved") return "Raise Invoice";
    if (stage === "Invoice Raised") return "Mark Paid";
    if (stage === "Active") return null;
    return `→ ${NEXT_STAGE[stage]}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Cases</h1>
          <p className="text-sm text-gray-500">{filtered.length} onboarding cases</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <div className="flex border border-gray-200 rounded-lg overflow-hidden">
            <button onClick={() => setView("kanban")} className={`px-3 py-1.5 text-xs flex items-center gap-1 ${view === "kanban" ? "bg-gray-100 text-gray-800" : "text-gray-500 hover:bg-gray-50"}`}>
              <Icon name="kanban" size={14} /> Kanban
            </button>
            <button onClick={() => setView("table")} className={`px-3 py-1.5 text-xs flex items-center gap-1 ${view === "table" ? "bg-gray-100 text-gray-800" : "text-gray-500 hover:bg-gray-50"}`}>
              <Icon name="table" size={14} /> Table
            </button>
          </div>
          <button onClick={exportCSV} className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">Export CSV</button>
          <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
            <Icon name="plus" size={14} /> New Case
          </button>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search cases..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          {["All", ...STAGES].map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>

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
                      <div className="text-xs text-gray-400 mb-2">{c.case_uid}</div>
                      <div className="flex items-center justify-between gap-1 flex-wrap">
                        <Badge text={c.status} />
                        <Badge text={c.invoice_status} />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
                        {actionLabel(stage) && (
                          <button onClick={() => advance(c)}
                            className="text-xs px-2 py-0.5 rounded border border-gray-200 hover:border-blue-300 hover:text-blue-600 text-gray-500">
                            {actionLabel(stage)}
                          </button>
                        )}
                        {c.status === "Active" ? (
                          <button onClick={() => setStatus(c, "Docs Pending")}
                            className="text-xs px-2 py-0.5 rounded border border-gray-200 hover:border-amber-300 hover:text-amber-600 text-gray-500">
                            Mark Docs Pending
                          </button>
                        ) : c.status === "Docs Pending" && (
                          <button onClick={() => setStatus(c, "Active")}
                            className="text-xs px-2 py-0.5 rounded border border-gray-200 hover:border-green-300 hover:text-green-600 text-gray-500">
                            Resume
                          </button>
                        )}
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
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Case</th>
                <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Company</th>
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
                  <td className="py-3 px-4 text-xs font-medium text-gray-800">{c.case_uid}</td>
                  <td className="py-3 px-4 text-xs text-gray-600">{c.company_name}</td>
                  <td className="py-3 px-4"><Badge text={c.stage} /></td>
                  <td className="py-3 px-4"><Badge text={c.status} /></td>
                  <td className="py-3 px-4"><Badge text={c.invoice_status} /></td>
                  <td className="py-3 px-4 text-xs text-right text-gray-600">{fmt(c.invoice_amount)}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1">
                      <button onClick={() => { setForm(c); setModal("edit"); }}
                        className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600">
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
            <button onClick={confirmRaiseInvoice} className="px-4 py-2 text-sm text-white rounded-lg font-medium" style={{ background: "#2B6D9A" }}>
              Raise Invoice
            </button>
          </div>
        </Modal>
      )}

      {modal && (
        <Modal title={modal === "new" ? "New Case" : `Edit ${form.case_uid}`} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Company Name" required><Input value={form.company_name || ""} onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))} /></Field>
            <Field label="Source">
              <Select value={form.source || "Other"} onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))}>
                {CASE_SOURCE_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Account">
              <Select value={form.account_id || ""} onChange={(e) => setForm((p) => ({ ...p, account_id: e.target.value ? +e.target.value : null }))}>
                <option value="">— None —</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Relationship Manager">
              <Select value={form.rm_id || ""} onChange={(e) => setForm((p) => ({ ...p, rm_id: e.target.value ? +e.target.value : null }))}>
                <option value="">— Unassigned —</option>
                {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            <Field label="Ops Owner">
              <Select value={form.ops_owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, ops_owner_id: e.target.value ? +e.target.value : null }))}>
                <option value="">— Unassigned —</option>
                {users.filter((u) => u.role === "ops").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            <Field label="Tags"><Input value={form.tags || ""} onChange={(e) => setForm((p) => ({ ...p, tags: e.target.value }))} /></Field>
          </div>
          <Field label="Notes"><Textarea value={form.notes || ""} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
