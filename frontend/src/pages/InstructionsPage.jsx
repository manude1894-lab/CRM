import React, { useEffect, useMemo, useState } from "react";
import { instructionsApi, casesApi, invoicesApi, accountsApi } from "../api/endpoints";
import { useMasters } from "../hooks/useMasters";
import { selectableCodes } from "../hooks/masterUtils";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";
import DocumentsPanel from "../components/DocumentsPanel";
import FeedbackPanel from "../components/FeedbackPanel";
import { INSTRUCTION_STATUS_OPTIONS, INSTRUCTION_TYPE_OPTIONS, fmtFull, fmtDate } from "../utils/constants";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";
import { useAuthStore } from "../store/auth";
import CsvImportModal from "../components/CsvImportModal";

// BRD §17 — a service request belongs to a client; the BVI case (and the Vistra dates) are optional.
const emptyForm = (accountId) => ({
  account_id: accountId || "",
  case_id: "",
  instruction_type: "",
  status: "Pending",
  document_shared: "",
  date_received: new Date().toISOString().split("T")[0],
  date_sent_to_vistra: "",
  date_received_from_vistra: "",
  date_completed: "",
  cost_amount: "",
  charge_amount: "",
  invoice_reference: "",
  invoice_id: "",
  comments: "",
});

// Strip blank-string fields to null so optional date/number columns don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(
  Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v])
);

const REQUEST_COLUMNS = [
  ["client_id", "Client ID"],
  ["company_name", "Company Name", "Entity", "Entity Name"],
  ["case_uid", "Case ID", "Case"],
  ["request_type", "Request Type", "Instruction Type", "Instruction"],
  ["status", "Status"],
  ["date_received", "Date Received", "Received"],
  ["date_sent_to_vistra", "Date Sent to Vistra", "Sent to Vistra"],
  ["date_received_from_vistra", "Date Received from Vistra", "Received from Vistra"],
  ["date_completed", "Date Completed", "Completed"],
  ["cost_amount", "Cost", "Cost Paid"],
  ["charge_amount", "Charge", "Charge Billed"],
  ["invoice_reference", "Invoice Reference", "Invoice Ref", "Invoice No"],
  ["comments", "Comments", "Notes"],
];

export default function InstructionsPage() {
  const [instructions, setInstructions] = useState([]);
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [importing, setImporting] = useState(false); // P6 — open requests from the Excel tracker
  const [cases, setCases] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [clientFilter, setClientFilter] = useState("");
  const requestTypes = useMasters("service_request_type", INSTRUCTION_TYPE_OPTIONS);
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
      const [instRes, caseRes, invRes, accRes] = await Promise.all([
        instructionsApi.list({ limit: 500 }),
        casesApi.list({ limit: 500 }),
        invoicesApi.list({ limit: 500 }),
        accountsApi.list({ limit: 500 }),
      ]);
      setInstructions(instRes.items || []);
      setCases(caseRes.items || []);
      setAccounts(accRes.items || []);
      setInvoices(invRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load service requests");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const caseById = useMemo(() => Object.fromEntries(cases.map((c) => [c.id, c])), [cases]);
  const accountById = useMemo(() => Object.fromEntries(accounts.map((a) => [a.id, a])), [accounts]);
  const clientCases = cases.filter((c) => !form.account_id || c.account_id === Number(form.account_id));
  const caseInvoices = useMemo(
    () => invoices.filter((inv) => inv.case_id === Number(form.case_id)),
    [invoices, form.case_id]
  );

  const filtered = instructions.filter((i) => {
    const matchStatus = statusFilter === "All" || i.status === statusFilter;
    const acc = accountById[i.account_id];
    const company = acc?.company_name || caseById[i.case_id]?.company_name || "";
    const matchSearch = search === "" || [company, acc?.client_id, i.instruction_type, i.invoice_reference, i.comments]
      .some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    return matchStatus && matchSearch && (!clientFilter || i.account_id === Number(clientFilter));
  });

  const openNew = () => { setForm(emptyForm(clientFilter)); setModal("new"); };
  const openEdit = (i) => { setForm({ ...i, account_id: i.account_id || "", case_id: i.case_id || "", charge_amount: i.charge_amount ?? "", cost_amount: i.cost_amount ?? "" }); setModal("edit"); };

  const save = async () => {
    if (!form.account_id && !form.case_id) return toast.error("Choose the client for this service request");
    if (!form.instruction_type) return toast.error("Choose the request type");
    try {
      const payload = cleanPayload(form);
      if (payload.invoice_id != null) payload.invoice_id = Number(payload.invoice_id);
      if (modal === "new") {
        await instructionsApi.create({ ...payload, account_id: payload.account_id ? Number(payload.account_id) : null,
          case_id: payload.case_id ? Number(payload.case_id) : null });
        toast.success("Service request created");
      } else {
        const { id, case_id, account_id, created_at, updated_at, ...patch } = payload;
        await instructionsApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const quickSetStatus = async (i, status) => {
    try { await instructionsApi.update(i.id, { status }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (id) => {
    if (!(await confirmDialog("Delete this service request?"))) return;
    try { await instructionsApi.delete(id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const counts = INSTRUCTION_STATUS_OPTIONS.reduce((acc, s) => {
    acc[s] = instructions.filter((i) => i.status === s).length;
    return acc;
  }, {});

  const totals = filtered.reduce((acc, i) => {
    acc.cost += Number(i.cost_amount || 0);
    acc.charge += Number(i.charge_amount || 0);
    return acc;
  }, { cost: 0, charge: 0 });
  totals.margin = totals.charge - totals.cost;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Service Requests</h1>
          <p className="text-sm text-gray-500">{filtered.length} of {instructions.length} service requests</p>
        </div>
        <div className="flex gap-2">
          {isAdmin && (
            <button onClick={() => setImporting(true)} className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">Import</button>
          )}
          <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#1a3a5c" }}>
          <Icon name="plus" size={14} /> New Service Request
        </button>
        </div>
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-48">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search company, type, invoice ref..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-brand-400" />
        </div>
        {["All", ...INSTRUCTION_STATUS_OPTIONS].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${statusFilter === s ? "text-white border-transparent" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}
            style={statusFilter === s ? { background: "#1a3a5c" } : {}}>
            {s} {s !== "All" && `(${counts[s] || 0})`}
          </button>
        ))}
        <select value={clientFilter} onChange={(e) => setClientFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-brand-400">
          <option value="">All clients</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.company_name}</option>)}
        </select>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-2 shadow-sm">
          <div className="text-[11px] text-gray-400 uppercase tracking-wide">Cost (to RA)</div>
          <div className="text-sm font-semibold text-gray-700">{fmtFull(totals.cost)}</div>
        </div>
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-2 shadow-sm">
          <div className="text-[11px] text-gray-400 uppercase tracking-wide">Charged (to client)</div>
          <div className="text-sm font-semibold text-gray-700">{fmtFull(totals.charge)}</div>
        </div>
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-2 shadow-sm">
          <div className="text-[11px] text-gray-400 uppercase tracking-wide">Margin</div>
          <div className={`text-sm font-semibold ${totals.margin < 0 ? "text-red-600" : "text-emerald-600"}`}>{fmtFull(totals.margin)}</div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Client</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Request Type</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Status</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Received</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Completed</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Cost</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Charge</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Margin</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Invoice Ref</th>
              <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={10} className="py-8 text-center text-sm text-gray-400">No service requests match this filter.</td></tr>
            )}
            {filtered.map((i) => (
              <tr key={i.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 px-4 text-xs">
                  <div className="font-medium text-gray-800">{accountById[i.account_id]?.company_name || caseById[i.case_id]?.company_name || "—"}</div>
                  <div className="text-gray-400">
                    <span className="font-mono">{accountById[i.account_id]?.client_id || ""}</span>
                    {i.case_id && <> {accountById[i.account_id]?.client_id ? "· " : ""}{caseById[i.case_id]?.case_uid}</>}
                  </div>
                </td>
                <td className="py-3 px-4 text-xs text-gray-600">{i.instruction_type}</td>
                <td className="py-3 px-4">
                  <select value={i.status} onChange={(e) => quickSetStatus(i, e.target.value)}
                    className="text-xs border-0 bg-transparent focus:outline-none cursor-pointer">
                    {INSTRUCTION_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </td>
                <td className="py-3 px-4 text-xs text-gray-500">{fmtDate(i.date_received) || "—"}</td>
                <td className="py-3 px-4 text-xs text-gray-500">{fmtDate(i.date_completed) || "—"}</td>
                <td className="py-3 px-4 text-xs text-right text-gray-500">{i.cost_amount != null ? fmtFull(i.cost_amount) : "—"}</td>
                <td className="py-3 px-4 text-xs text-right text-gray-600">{i.charge_amount != null ? fmtFull(i.charge_amount) : "—"}</td>
                <td className="py-3 px-4 text-xs text-right text-gray-500">
                  {i.charge_amount != null || i.cost_amount != null
                    ? fmtFull(Number(i.charge_amount || 0) - Number(i.cost_amount || 0))
                    : "—"}
                </td>
                <td className="py-3 px-4 text-xs text-gray-500">{i.invoice_reference || "—"}</td>
                <td className="py-3 px-4">
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(i)} className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600">
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

      {importing && (
        <CsvImportModal title="Import open service requests" columns={REQUEST_COLUMNS} required={["request_type"]}
          templateName="service-requests-template.csv" onRun={instructionsApi.importRequests} onClose={() => setImporting(false)} onDone={load} />
      )}

      {modal && (
        <Modal title={modal === "new" ? "New Service Request" : "Edit Service Request"} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Client" required>
              <Select value={form.account_id || ""} disabled={modal === "edit"} onChange={(e) => setForm((p) => ({ ...p, account_id: e.target.value, case_id: "" }))}>
                <option value="">— choose client —</option>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.client_id ? `${a.client_id} – ` : ""}{a.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Case / entity (optional)">
              <Select value={form.case_id || ""} disabled={modal === "edit"} onChange={(e) => setForm((p) => ({ ...p, case_id: e.target.value }))}>
                <option value="">— none —</option>
                {clientCases.map((c) => <option key={c.id} value={c.id}>{c.case_uid} – {c.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Request Type" required>
              <Select value={form.instruction_type || ""} onChange={(e) => setForm((p) => ({ ...p, instruction_type: e.target.value }))}>
                <option value="">— choose —</option>
                {selectableCodes(requestTypes.items, form.instruction_type).map((t) => <option key={t} value={t}>{requestTypes.labelOf(t)}</option>)}
              </Select>
            </Field>
            <Field label="Status">
              <Select value={form.status || "Pending"} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {INSTRUCTION_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Cost (to registered agent)">
              <Input type="number" min="0" step="0.01" value={form.cost_amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, cost_amount: e.target.value }))} />
            </Field>
            <Field label="Charge (to client)">
              <Input type="number" min="0" step="0.01" value={form.charge_amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, charge_amount: e.target.value }))} />
            </Field>
            <Field label="Date Received">
              <Input type="date" value={form.date_received || ""} onChange={(e) => setForm((p) => ({ ...p, date_received: e.target.value }))} />
            </Field>
            {form.case_id && (<>
            <Field label="Date Sent to Vistra">
              <Input type="date" value={form.date_sent_to_vistra || ""} onChange={(e) => setForm((p) => ({ ...p, date_sent_to_vistra: e.target.value }))} />
            </Field>
            <Field label="Date Received from Vistra">
              <Input type="date" value={form.date_received_from_vistra || ""} onChange={(e) => setForm((p) => ({ ...p, date_received_from_vistra: e.target.value }))} />
            </Field>
            </>)}
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

          {!form.case_id && <p className="text-[11px] text-gray-400 -mt-2 mb-3">Without a case, the Vistra dates don't apply and a completed charged request is invoiced manually.</p>}

          {modal === "edit" && form.id && form.case_id && (
            <div className="border-t border-gray-100 pt-3 mb-1">
              <p className="text-xs font-semibold text-gray-600 mb-2">Attachments <span className="text-gray-400 font-normal">· issued docs, filed-return confirmations</span></p>
              <DocumentsPanel caseId={Number(form.case_id)} scope={{ instruction_id: form.id }} defaultCategory="Filed Return / Confirmation" />
            </div>
          )}

          {modal === "edit" && form.id && form.case_id && (
            <div className="border-t border-gray-100 pt-3 mb-1">
              <p className="text-xs font-semibold text-gray-600 mb-2">Client Feedback <span className="text-gray-400 font-normal">· logged by staff, not client-submitted</span></p>
              <FeedbackPanel caseId={Number(form.case_id)} instructionId={form.id} />
            </div>
          )}

          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
