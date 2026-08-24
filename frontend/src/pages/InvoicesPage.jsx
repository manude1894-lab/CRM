import React, { useEffect, useMemo, useState } from "react";
import { invoicesApi, instructionsApi, casesApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";
import { INVOICE_LEDGER_STATUS_OPTIONS, fmtFull } from "../utils/constants";

const emptyForm = (cases) => ({
  case_id: cases[0]?.id,
  invoice_number: "",
  description: "",
  amount: "",
  status: "Draft",
  raised_date: "",
  due_date: "",
  paid_date: "",
  notes: "",
});

// Strip blank-string fields to null so optional date/number columns don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState([]);
  const [instructions, setInstructions] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [invRes, instRes, caseRes] = await Promise.all([
        invoicesApi.list({ limit: 500 }),
        instructionsApi.list({ limit: 500 }),
        casesApi.list({ limit: 500 }),
      ]);
      setInvoices(invRes.items || []);
      setInstructions(instRes.items || []);
      setCases(caseRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load invoices");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const caseById = useMemo(() => Object.fromEntries(cases.map((c) => [c.id, c])), [cases]);
  const linkedCount = useMemo(() => {
    const counts = {};
    instructions.forEach((i) => { if (i.invoice_id) counts[i.invoice_id] = (counts[i.invoice_id] || 0) + 1; });
    return counts;
  }, [instructions]);

  const filtered = invoices.filter((inv) => {
    const matchStatus = statusFilter === "All" || inv.status === statusFilter;
    const company = caseById[inv.case_id]?.company_name || "";
    const matchSearch = search === "" || [company, inv.invoice_number, inv.description]
      .some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    return matchStatus && matchSearch;
  });

  const totalOutstanding = invoices
    .filter((i) => i.status === "Raised" || i.status === "Overdue")
    .reduce((sum, i) => sum + Number(i.amount || 0), 0);

  const openNew = () => { setForm(emptyForm(cases)); setModal("new"); };
  const openEdit = (inv) => { setForm({ ...inv }); setModal("edit"); };

  const save = async () => {
    try {
      const payload = cleanPayload(form);
      if (modal === "new") {
        await invoicesApi.create({ ...payload, case_id: Number(payload.case_id) });
      } else {
        const { id, case_id, created_at, updated_at, ...patch } = payload;
        await invoicesApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const quickSetStatus = async (inv, status) => {
    try {
      const patch = { status };
      if (status === "Paid" && !inv.paid_date) patch.paid_date = new Date().toISOString().split("T")[0];
      await invoicesApi.update(inv.id, patch);
      load();
    } catch (e) { alert(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (id) => {
    if (!confirm("Delete this invoice? Any linked instructions will be unlinked.")) return;
    try { await invoicesApi.delete(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const counts = INVOICE_LEDGER_STATUS_OPTIONS.reduce((acc, s) => {
    acc[s] = invoices.filter((i) => i.status === s).length;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Invoices</h1>
          <p className="text-sm text-gray-500">
            {filtered.length} of {invoices.length} invoices · {fmtFull(totalOutstanding)} outstanding (Raised + Overdue)
          </p>
        </div>
        <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={14} /> New Invoice
        </button>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-48">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search company, invoice #, description..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-400" />
        </div>
        {["All", ...INVOICE_LEDGER_STATUS_OPTIONS].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${statusFilter === s ? "text-white border-transparent" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
            style={statusFilter === s ? { background: "#2B6D9A" } : {}}>
            {s} {s !== "All" && `(${counts[s] || 0})`}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Entity</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Invoice #</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Description</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Status</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Amount</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Raised</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Paid</th>
              <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={8} className="py-8 text-center text-sm text-gray-400">No invoices match this filter.</td></tr>
            )}
            {filtered.map((inv) => (
              <tr key={inv.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 px-4 text-xs">
                  <div className="font-medium text-gray-800">{caseById[inv.case_id]?.company_name || "—"}</div>
                  <div className="text-gray-400">{caseById[inv.case_id]?.case_uid}</div>
                </td>
                <td className="py-3 px-4 text-xs text-gray-600">
                  {inv.invoice_number || "—"}
                  {linkedCount[inv.id] > 0 && (
                    <div className="text-gray-400">{linkedCount[inv.id]} instruction{linkedCount[inv.id] > 1 ? "s" : ""} linked</div>
                  )}
                </td>
                <td className="py-3 px-4 text-xs text-gray-600 max-w-xs truncate">{inv.description || "—"}</td>
                <td className="py-3 px-4">
                  <select value={inv.status} onChange={(e) => quickSetStatus(inv, e.target.value)}
                    className="text-xs border-0 bg-transparent focus:outline-none cursor-pointer">
                    {INVOICE_LEDGER_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td className="py-3 px-4 text-xs text-right text-gray-600">{fmtFull(inv.amount)}</td>
                <td className="py-3 px-4 text-xs text-gray-500">{inv.raised_date || "—"}</td>
                <td className="py-3 px-4 text-xs text-gray-500">{inv.paid_date || "—"}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(inv)} className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600">
                      <Icon name="edit" size={14} />
                    </button>
                    <button onClick={() => remove(inv.id)} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                      <Icon name="del" size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <Modal title={modal === "new" ? "New Invoice" : "Edit Invoice"} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Entity" required>
              <Select value={form.case_id || ""} disabled={modal === "edit"} onChange={(e) => setForm((p) => ({ ...p, case_id: e.target.value }))}>
                {cases.map((c) => <option key={c.id} value={c.id}>{c.case_uid} – {c.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Invoice Number">
              <Input value={form.invoice_number || ""} onChange={(e) => setForm((p) => ({ ...p, invoice_number: e.target.value }))} placeholder="e.g. 2024-TCS-00005" />
            </Field>
            <Field label="Status">
              <Select value={form.status || "Draft"} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {INVOICE_LEDGER_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Amount" required>
              <Input type="number" min="0" step="0.01" value={form.amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, amount: e.target.value }))} />
            </Field>
            <Field label="Raised Date">
              <Input type="date" value={form.raised_date || ""} onChange={(e) => setForm((p) => ({ ...p, raised_date: e.target.value }))} />
            </Field>
            <Field label="Due Date">
              <Input type="date" value={form.due_date || ""} onChange={(e) => setForm((p) => ({ ...p, due_date: e.target.value }))} />
            </Field>
            <Field label="Paid Date">
              <Input type="date" value={form.paid_date || ""} onChange={(e) => setForm((p) => ({ ...p, paid_date: e.target.value }))} />
            </Field>
          </div>
          <Field label="Description"><Input value={form.description || ""} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} placeholder="e.g. COI + COGS issuance, notarization" /></Field>
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
