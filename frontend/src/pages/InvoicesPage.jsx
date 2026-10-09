import React, { useEffect, useMemo, useState } from "react";
import { accountsApi, documentsApi, instructionsApi, invoicesApi } from "../api/endpoints";
import { Button, EmptyState, ErrorBanner, Field, FilterBar, Icon, Input, Modal, PageHeader, SearchInput, Select, Spinner, Textarea, DateInput } from "../components/ui";
import { fmtDate } from "../utils/constants";
import { useAuthStore } from "../store/auth";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";

const CURRENCIES = ["AED", "USD", "EUR", "GBP", "INR", "SGD"];
const STATUSES = ["Requested", "Draft", "Raised", "Paid", "Overdue"];
const STATUS_STYLE = {
  Requested: "bg-amber-100 text-amber-800", Draft: "bg-amber-50 text-amber-700", Raised: "bg-blue-50 text-blue-700",
  Paid: "bg-emerald-50 text-emerald-700", Overdue: "bg-red-50 text-red-700",
};
const money = (currency, amount) => `${currency || "AED"} ${Number(amount || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/**
 * Triam BRD mark-up §16 — the Invoice module. The RM / Sales requests an invoice for a client onboarding or a
 * service request and attaches the pricing approvals (the instruction to Accounts); Accounts records the
 * Invoice No, Date, Currency and Amount with the invoice file, and the payment. Front-end staff download
 * the invoice from here to send it to the client.
 */
export default function InvoicesPage() {
  const accountsTeam = useAuthStore((s) => s.can("invoice.manage"));
  const [invoices, setInvoices] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [requesting, setRequesting] = useState(false);
  const [raising, setRaising] = useState(null);
  const [files, setFiles] = useState(null); // invoice whose attachments are open

  const load = () => invoicesApi.list({ limit: 500 }).then((r) => { setInvoices(r.items || []); setError(null); })
    .catch((e) => setError(e.response?.data?.detail || "Failed to load invoices"));
  useEffect(() => { load(); }, []);

  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!invoices) return <Spinner />;

  const q = search.trim().toLowerCase();
  const rows = invoices.filter((i) => (!status || i.status === status)
    && (!q || [i.company_name, i.client_id, i.invoice_number, i.description].some((v) => (v || "").toLowerCase().includes(q))));
  const waiting = invoices.filter((i) => ["Requested", "Draft"].includes(i.status)).length;
  const outstanding = invoices.filter((i) => ["Raised", "Overdue"].includes(i.status));

  const markPaid = async (inv) => {
    if (!(await confirmDialog(`Record payment of ${inv.invoice_number} (${money(inv.currency, inv.amount)})?`))) return;
    try { await invoicesApi.paid(inv.id, {}); toast.success("Payment recorded"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not record the payment"); }
  };
  const remove = async (inv) => {
    if (!(await confirmDialog(`Delete this invoice ${inv.status === "Requested" ? "request" : ""}?`))) return;
    try { await invoicesApi.delete(inv.id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not delete"); }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Invoices"
        subtitle={<>{waiting} waiting for Accounts · {outstanding.length} raised and unpaid</>}
        actions={<Button variant="primary" onClick={() => setRequesting(true)}><Icon name="plus" size={15} /> Request invoice</Button>} />
      <FilterBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search client, invoice no. or description…" />
        <div className="w-44">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s}>{s}</option>)}
          </Select>
        </div>
      </FilterBar>

      {rows.length === 0 ? (
        <EmptyState title="No invoices" text="Request an invoice for a new client or a completed service request; Accounts is notified." />
      ) : (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
              {["Client", "Description", "Amount", "Status", "Invoice", "Requested", ""].map((h) => (
                <th key={h} className={`py-2.5 px-3 font-semibold ${h === "Amount" ? "text-right" : "text-left"}`}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {rows.map((i) => (
                <tr key={i.id} className="border-b border-gray-50 align-top">
                  <td className="py-2.5 px-3">
                    <div className="font-medium text-gray-800">{i.company_name || "—"}</div>
                    <div className="text-[11px] font-mono text-gray-400">{i.client_id}</div>
                  </td>
                  <td className="py-2.5 px-3 text-xs text-gray-600 max-w-xs">{i.description}{i.notes && <div className="text-gray-400">{i.notes}</div>}</td>
                  <td className="py-2.5 px-3 text-right whitespace-nowrap">{money(i.currency, i.amount)}</td>
                  <td className="py-2.5 px-3"><span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${STATUS_STYLE[i.status] || "bg-gray-100"}`}>{i.status}</span></td>
                  <td className="py-2.5 px-3 text-xs text-gray-600 whitespace-nowrap">
                    {i.invoice_number ? <><div className="font-mono">{i.invoice_number}</div><div className="text-gray-400">{fmtDate(i.raised_date)}{i.paid_date ? ` · paid ${fmtDate(i.paid_date)}` : ""}</div></> : "—"}
                  </td>
                  <td className="py-2.5 px-3 text-xs text-gray-500 whitespace-nowrap">{i.requested_by_name || "—"}<div className="text-gray-400">{fmtDate(i.requested_at || i.created_at)}</div></td>
                  <td className="py-2.5 px-3 text-right whitespace-nowrap">
                    <div className="flex justify-end gap-1.5">
                      <button onClick={() => setFiles(i)} className="px-2 py-1 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">
                        Files{i.attachment_count ? ` (${i.attachment_count})` : ""}
                      </button>
                      {accountsTeam && ["Requested", "Draft"].includes(i.status) && (
                        <button onClick={() => setRaising(i)} className="px-2 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Raise</button>
                      )}
                      {accountsTeam && ["Raised", "Overdue"].includes(i.status) && (
                        <button onClick={() => markPaid(i)} className="px-2 py-1 text-xs border border-emerald-300 text-emerald-700 rounded-lg hover:bg-emerald-50">Mark paid</button>
                      )}
                      {i.status !== "Paid" && (accountsTeam || ["Requested", "Draft"].includes(i.status)) && (
                        <button onClick={() => remove(i)} title="Delete" className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={13} /></button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {requesting && <RequestModal onClose={() => setRequesting(false)} onDone={() => { setRequesting(false); load(); }} />}
      {raising && <RaiseModal invoice={raising} onClose={() => setRaising(null)} onDone={() => { setRaising(null); load(); }} />}
      {files && <FilesModal invoice={files} accountsTeam={accountsTeam} onClose={() => { setFiles(null); load(); }} />}
    </div>
  );
}

/** RM / Sales — the instruction to Accounts, with the pricing approvals. */
function RequestModal({ onClose, onDone }) {
  const [clients, setClients] = useState([]);
  const [requests, setRequests] = useState([]);
  const [form, setForm] = useState({ account_id: "", instruction_id: "", description: "", amount: "", currency: "AED", notes: "" });
  const [approvals, setApprovals] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => { accountsApi.list({ limit: 1000 }).then((r) => setClients(r.items || r || [])).catch(() => {}); }, []);
  useEffect(() => {
    if (!form.account_id) return setRequests([]);
    instructionsApi.list({ account_id: form.account_id, limit: 200 }).then((r) => setRequests((r.items || []).filter((x) => !x.invoice_id))).catch(() => {});
  }, [form.account_id]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const pickRequest = (e) => {
    const sr = requests.find((x) => String(x.id) === e.target.value);
    setForm((f) => ({ ...f, instruction_id: e.target.value, description: sr ? sr.instruction_type : f.description, amount: sr?.charge_amount ?? f.amount }));
  };

  const submit = async () => {
    if (!form.account_id || !form.description.trim() || form.amount === "") return toast.error("Choose the client and enter the description and amount");
    setBusy(true);
    try {
      const inv = await invoicesApi.request({
        account_id: Number(form.account_id), instruction_id: form.instruction_id ? Number(form.instruction_id) : null,
        description: form.description.trim(), amount: form.amount, currency: form.currency, notes: form.notes.trim() || null,
      });
      for (const f of approvals) await invoicesApi.attach(inv.id, f, "Pricing Approval");
      toast.success("Invoice requested — Accounts has been notified");
      onDone();
    } catch (e) { toast.error(e.response?.data?.detail || "Request failed"); } finally { setBusy(false); }
  };

  return (
    <Modal title="Request an invoice" onClose={onClose}>
      <p className="text-xs text-gray-500 -mt-2 mb-3">Accounts is notified and raises the invoice. Attach the pricing approval for the amount.</p>
      <Field label="Client" required>
        <Select value={form.account_id} onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value, instruction_id: "" }))}>
          <option value="">— choose —</option>
          {clients.map((c) => <option key={c.id} value={c.id}>{c.company_name}{c.client_id ? ` (${c.client_id})` : ""}</option>)}
        </Select>
      </Field>
      <Field label="For a service request (optional — leave empty for the onboarding invoice)">
        <Select value={form.instruction_id} onChange={pickRequest} disabled={!form.account_id}>
          <option value="">— client onboarding / other —</option>
          {requests.map((r) => <option key={r.id} value={r.id}>{r.instruction_type} · {r.status}{r.charge_amount ? ` · ${r.charge_amount}` : ""}</option>)}
        </Select>
      </Field>
      <Field label="Description" required><Input value={form.description} onChange={set("description")} maxLength={500} placeholder="e.g. Company formation — ADGM SPV" /></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Amount" required><Input type="number" min="0" step="0.01" value={form.amount} onChange={set("amount")} /></Field>
        <Field label="Currency"><Select value={form.currency} onChange={set("currency")}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select></Field>
      </div>
      <Field label="Notes for Accounts"><Textarea rows={2} value={form.notes} onChange={set("notes")} maxLength={2000} /></Field>
      <Field label="Pricing approval(s)">
        <input type="file" multiple accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.bmp" onChange={(e) => setApprovals([...e.target.files])}
          className="text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
      </Field>
      <div className="flex justify-end gap-2 mt-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={submit} disabled={busy}>{busy ? "Sending…" : "Send to Accounts"}</Button>
      </div>
    </Modal>
  );
}

/** Accounts — record the issued invoice. */
function RaiseModal({ invoice, onClose, onDone }) {
  const [form, setForm] = useState({ invoice_number: "", invoice_date: new Date().toISOString().slice(0, 10), currency: invoice.currency || "AED", amount: invoice.amount ?? "", due_date: "" });
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const submit = async () => {
    if (!form.invoice_number.trim() || !form.invoice_date || form.amount === "") return toast.error("Enter the invoice number, date and amount");
    if (!file && !invoice.attachment_count) return toast.error("Attach the invoice file");
    setBusy(true);
    try {
      if (file) await invoicesApi.attach(invoice.id, file, "Invoice");
      await invoicesApi.raise(invoice.id, { ...form, due_date: form.due_date || null });
      toast.success("Invoice raised — the requester can download it");
      onDone();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not raise the invoice"); } finally { setBusy(false); }
  };
  return (
    <Modal title={`Raise invoice — ${invoice.company_name}`} onClose={onClose}>
      <p className="text-xs text-gray-500 -mt-2 mb-3">{invoice.description} · requested {money(invoice.currency, invoice.amount)} by {invoice.requested_by_name || "—"}</p>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Invoice No." required><Input value={form.invoice_number} onChange={set("invoice_number")} maxLength={50} /></Field>
        <Field label="Invoice Date" required><DateInput value={form.invoice_date} onChange={set("invoice_date")} /></Field>
        <Field label="Amount" required><Input type="number" min="0" step="0.01" value={form.amount} onChange={set("amount")} /></Field>
        <Field label="Currency"><Select value={form.currency} onChange={set("currency")}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select></Field>
        <Field label="Due Date"><DateInput value={form.due_date} onChange={set("due_date")} /></Field>
      </div>
      <Field label="Invoice file" required>
        <input type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.bmp" onChange={(e) => setFile(e.target.files[0] || null)}
          className="text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
      </Field>
      <div className="flex justify-end gap-2 mt-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={submit} disabled={busy}>{busy ? "Saving…" : "Raise invoice"}</Button>
      </div>
    </Modal>
  );
}

/** Pricing approvals and the invoice file, to download; RM may add approvals while the request is open. */
function FilesModal({ invoice, accountsTeam, onClose }) {
  const [docs, setDocs] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => invoicesApi.attachments(invoice.id).then(setDocs).catch(() => setDocs([]));
  useEffect(() => { load(); }, [invoice.id]);
  const canAddApproval = ["Requested", "Draft"].includes(invoice.status) || accountsTeam;
  const add = async (file, kind) => {
    if (!file) return;
    setBusy(true);
    try { await invoicesApi.attach(invoice.id, file, kind); toast.success(`${kind} attached`); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Upload failed"); } finally { setBusy(false); }
  };
  const groups = useMemo(() => ({ "Invoice": (docs || []).filter((d) => d.category === "Invoice"), "Pricing Approval": (docs || []).filter((d) => d.category === "Pricing Approval") }), [docs]);
  return (
    <Modal title={`Files — ${invoice.company_name}`} onClose={onClose}>
      {docs === null ? <Spinner /> : Object.entries(groups).map(([kind, list]) => (
        <div key={kind} className="mb-3">
          <div className="text-xs font-semibold text-gray-600 mb-1">{kind === "Invoice" ? "Invoice" : "Pricing approvals"}</div>
          {list.length === 0 ? <p className="text-xs text-gray-400">None yet.</p> : list.map((d) => (
            <button key={d.id} onClick={() => documentsApi.download(d.id, d.filename)} className="flex items-center gap-1.5 text-xs text-brand-600 hover:underline">
              <Icon name="download" size={12} />{d.filename}<span className="text-gray-400">· {fmtDate(d.created_at)}</span>
            </button>
          ))}
          {((kind === "Invoice" && accountsTeam) || (kind === "Pricing Approval" && canAddApproval)) && (
            <input type="file" disabled={busy} accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.bmp" onChange={(e) => add(e.target.files[0], kind)}
              className="mt-1 text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
          )}
        </div>
      ))}
      <div className="flex justify-end"><Button onClick={onClose}>Close</Button></div>
    </Modal>
  );
}
