import React, { useEffect, useMemo, useState } from "react";
import { instructionsApi, casesApi, invoicesApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";
import { INSTRUCTION_STATUS_OPTIONS, INSTRUCTION_TYPE_OPTIONS, fmtFull } from "../utils/constants";

const emptyForm = (cases) => ({
  case_id: cases[0]?.id,
  instruction_type: INSTRUCTION_TYPE_OPTIONS[0],
  status: "Pending",
  document_shared: "",
  date_received: new Date().toISOString().split("T")[0],
  date_sent_to_vistra: "",
  date_received_from_vistra: "",
  date_completed: "",
  charge_amount: "",
  invoice_reference: "",
  invoice_id: "",
  comments: "",
});

// Strip blank-string fields to null so optional date/number columns don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

export default function InstructionsPage() {
  const [instructions, setInstructions] = useState([]);
  const [cases, setCases] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [instRes, caseRes, invRes] = await Promise.all([
        instructionsApi.list({ limit: 500 }),
        casesApi.list({ limit: 500 }),
        invoicesApi.list({ limit: 500 }),
      ]);
      setInstructions(instRes.items || []);
      setCases(caseRes.items || []);
      setInvoices(invRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load instructions");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const caseById = useMemo(() => Object.fromEntries(cases.map((c) => [c.id, c])), [cases]);
  const caseInvoices = useMemo(
    () => invoices.filter((inv) => inv.case_id === Number(form.case_id)),
    [invoices, form.case_id]
  );

  const filtered = instructions.filter((i) => {
    const matchStatus = statusFilter === "All" || i.status === statusFilter;
    const company = caseById[i.case_id]?.company_name || "";
    const matchSearch = search === "" || [company, i.instruction_type, i.invoice_reference, i.comments]
      .some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    return matchStatus && matchSearch;
  });

  const openNew = () => { setForm(emptyForm(cases)); setModal("new"); };
  const openEdit = (i) => { setForm({ ...i, charge_amount: i.charge_amount ?? "" }); setModal("edit"); };

  const save = async () => {
    try {
      const payload = cleanPayload(form);
      if (payload.invoice_id != null) payload.invoice_id = Number(payload.invoice_id);
      if (modal === "new") {
        await instructionsApi.create({ ...payload, case_id: Number(payload.case_id) });
      } else {
        const { id, case_id, created_at, updated_at, ...patch } = payload;
        await instructionsApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const quickSetStatus = async (i, status) => {
    try { await instructionsApi.update(i.id, { status }); load(); }
    catch (e) { alert(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (id) => {
    if (!confirm("Delete this instruction?")) return;
    try { await instructionsApi.delete(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const counts = INSTRUCTION_STATUS_OPTIONS.reduce((acc, s) => {
    acc[s] = instructions.filter((i) => i.status === s).length;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Instruction Tracker</h1>
          <p className="text-sm text-gray-500">{filtered.length} of {instructions.length} service requests</p>
        </div>
        <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={14} /> New Instruction
        </button>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-48">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search company, type, invoice ref..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-400" />
        </div>
        {["All", ...INSTRUCTION_STATUS_OPTIONS].map((s) => (
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
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Instruction Type</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Status</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Received</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Completed</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Charge</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Invoice Ref</th>
              <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={8} className="py-8 text-center text-sm text-gray-400">No instructions match this filter.</td></tr>
            )}
            {filtered.map((i) => (
              <tr key={i.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 px-4 text-xs">
                  <div className="font-medium text-gray-800">{caseById[i.case_id]?.company_name || "—"}</div>
                  <div className="text-gray-400">{caseById[i.case_id]?.case_uid}</div>
                </td>
                <td className="py-3 px-4 text-xs text-gray-600">{i.instruction_type}</td>
                <td className="py-3 px-4">
                  <select value={i.status} onChange={(e) => quickSetStatus(i, e.target.value)}
                    className="text-xs border-0 bg-transparent focus:outline-none cursor-pointer">
                    {INSTRUCTION_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td className="py-3 px-4 text-xs text-gray-500">{i.date_received || "—"}</td>
                <td className="py-3 px-4 text-xs text-gray-500">{i.date_completed || "—"}</td>
                <td className="py-3 px-4 text-xs text-right text-gray-600">{i.charge_amount != null ? fmtFull(i.charge_amount) : "—"}</td>
                <td className="py-3 px-4 text-xs text-gray-500">{i.invoice_reference || "—"}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(i)} className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600">
                      <Icon name="edit" size={14} />
                    </button>
                    <button onClick={() => remove(i.id)} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
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
        <Modal title={modal === "new" ? "New Instruction" : `Edit Instruction`} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Entity" required>
              <Select value={form.case_id || ""} disabled={modal === "edit"} onChange={(e) => setForm((p) => ({ ...p, case_id: e.target.value }))}>
                {cases.map((c) => <option key={c.id} value={c.id}>{c.case_uid} – {c.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Instruction Type" required>
              <Select value={form.instruction_type || ""} onChange={(e) => setForm((p) => ({ ...p, instruction_type: e.target.value }))}>
                {INSTRUCTION_TYPE_OPTIONS.map((t) => <option key={t}>{t}</option>)}
              </Select>
            </Field>
            <Field label="Status">
              <Select value={form.status || "Pending"} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {INSTRUCTION_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Charge Amount">
              <Input type="number" min="0" step="0.01" value={form.charge_amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, charge_amount: e.target.value }))} />
            </Field>
            <Field label="Date Received">
              <Input type="date" value={form.date_received || ""} onChange={(e) => setForm((p) => ({ ...p, date_received: e.target.value }))} />
            </Field>
            <Field label="Date Sent to Vistra">
              <Input type="date" value={form.date_sent_to_vistra || ""} onChange={(e) => setForm((p) => ({ ...p, date_sent_to_vistra: e.target.value }))} />
            </Field>
            <Field label="Date Received from Vistra">
              <Input type="date" value={form.date_received_from_vistra || ""} onChange={(e) => setForm((p) => ({ ...p, date_received_from_vistra: e.target.value }))} />
            </Field>
            <Field label="Date Completed">
              <Input type="date" value={form.date_completed || ""} onChange={(e) => setForm((p) => ({ ...p, date_completed: e.target.value }))} />
            </Field>
            <Field label="Invoice Reference">
              <Input value={form.invoice_reference || ""} onChange={(e) => setForm((p) => ({ ...p, invoice_reference: e.target.value }))} placeholder="e.g. 2024-TCS-00005" />
            </Field>
            <Field label="Linked Invoice (ledger)">
              <Select value={form.invoice_id || ""} onChange={(e) => setForm((p) => ({ ...p, invoice_id: e.target.value }))}>
                <option value="">— None —</option>
                {caseInvoices.map((inv) => <option key={inv.id} value={inv.id}>{inv.invoice_number || `Invoice #${inv.id}`} ({inv.status})</option>)}
              </Select>
            </Field>
            <Field label="Document Shared">
              <Input value={form.document_shared || ""} onChange={(e) => setForm((p) => ({ ...p, document_shared: e.target.value }))} placeholder="e.g. Company docs (COI, MoA, ROM)" />
            </Field>
          </div>
          <Field label="Comments"><Textarea value={form.comments || ""} onChange={(e) => setForm((p) => ({ ...p, comments: e.target.value }))} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
