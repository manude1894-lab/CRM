import React, { useEffect, useMemo, useState } from "react";
import { instructionsApi, invoicesApi, accountsApi, documentsApi } from "../api/endpoints";
import { useMasters } from "../hooks/useMasters";
import { Icon, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, PageHeader, DateInput } from "../components/ui";
import MoneyInput from "../components/MoneyInput";
import { fmtDate, fmtMoney } from "../utils/constants";
import { useRequestOptions, pickableStatuses, firstOpenStatus, requestLabel, clientEntities, takesRequests } from "../hooks/useRequestOptions";
import { toast } from "../store/toast";
import { useAuthStore } from "../store/auth";
import { reasonDialog } from "../store/confirm";

// BRD §15 — service requests. Request types and statuses follow the Triam entity handling the request
// (Triam's "Service Requests - Triam Entities" list, kept as master data). Requests open once Compliance
// has approved the client (Triam, 12-11-2026).
//
// Invoicing follows Triam's Invoice Box template (11-11-2026): the RM records the charge (excluding VAT)
// with its currency, the client's payment and any service provider, and Submit sends the request to the
// Accountant's queue. The Accountant fills the invoice in the same window: Save keeps it, Send to RM
// raises it and tells the RM.
const CLOSED = ["Dropped", "Completed"];
const WITH_ACCOUNTANT = ["Requested", "Draft"];
const SENT_TO_RM = ["Raised", "Paid", "Overdue"];
const INVOICING = {
  "": "All invoicing",
  none: "Not submitted",
  accountant: "With the Accountant",
  sent: "Invoice sent to RM",
};

const emptyForm = (accountId) => ({
  account_id: accountId || "",
  triam_entity: "",
  instruction_type: "",
  other_description: "",
  status: "",
  date_received: new Date().toISOString().split("T")[0],
  date_completed: "",
  charge_amount: "",
  charge_currency: "AED",
  amount_paid: "",
  amount_paid_currency: "AED",
  payment_received_date: "",
  service_provider_involved: null,
  service_provider_name: "",
  service_provider_amount: "",
  service_provider_currency: "AED",
  comments: "",
});

// Fields the server sets; never sent back.
const SERVER_FIELDS = ["id", "account_id", "created_at", "updated_at", "cancel_reason", "invoice_id", "submitted_at", "submitted_by_id"];

// Blank strings go as null so optional date / number fields don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v]));
const toForm = (i) => Object.fromEntries(Object.entries({ ...emptyForm(), ...i }).map(([k, v]) => [k, v ?? (k === "service_provider_involved" ? null : "")]));

const invoicingOf = (inv) => (!inv || inv.status === "Cancelled" ? "none" : WITH_ACCOUNTANT.includes(inv.status) ? "accountant" : "sent");

export default function InstructionsPage() {
  const readOnly = useAuthStore((s) => s.isReadOnly());
  const accountant = useAuthStore((s) => s.can("invoice.manage"));
  const [instructions, setInstructions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [clientFilter, setClientFilter] = useState("");
  const requestTypes = useMasters("service_request_type", []);
  const triamEntities = useMasters("triam_entity", []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("All");
  const [invoicingFilter, setInvoicingFilter] = useState("");
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [instRes, invRes, accRes] = await Promise.all([
        instructionsApi.list({ limit: 500 }),
        invoicesApi.list({ limit: 500 }),
        accountsApi.list({ limit: 500 }),
      ]);
      setInstructions(instRes.items || []);
      setAccounts(accRes.items || []);
      setInvoices(invRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load service requests");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const accountById = useMemo(() => Object.fromEntries(accounts.map((a) => [a.id, a])), [accounts]);
  const invoiceById = useMemo(() => Object.fromEntries(invoices.map((inv) => [inv.id, inv])), [invoices]);
  const optionsFor = useRequestOptions([...instructions.map((i) => i.triam_entity), form.triam_entity]);
  const formOpts = optionsFor(form.triam_entity);
  // Triam input 19-10-2026: the Triam entity is chosen first, then one of the clients it serves.
  const activeEntities = triamEntities.items.filter((e) => e.is_active !== false).map((e) => e.code);
  const entityClients = accounts.filter((a) => (modal === "edit" || takesRequests(a))
    && (!form.triam_entity || clientEntities(a).includes(form.triam_entity)));
  const allStatuses = [...new Set(instructions.map((i) => i.status))];
  // A new entity resets the type and status to that entity's lists, and the client if that entity doesn't serve it.
  const chooseEntity = (entity) => setForm((p) => ({ ...p, triam_entity: entity, instruction_type: "", other_description: "", status: "",
    ...(p.account_id && !clientEntities(accountById[p.account_id]).includes(entity) ? { account_id: "" } : {}) }));
  const set = (k) => (v) => setForm((p) => ({ ...p, [k]: v }));
  // The other amounts follow the charge's currency until they are filled in.
  const setChargeCurrency = (v) => setForm((p) => ({ ...p, charge_currency: v,
    ...(p.amount_paid === "" ? { amount_paid_currency: v } : {}), ...(p.service_provider_amount === "" ? { service_provider_currency: v } : {}) }));

  const filtered = instructions.filter((i) => {
    const acc = accountById[i.account_id];
    const matchSearch = search === "" || [acc?.company_name, acc?.client_id, i.instruction_type, i.other_description, i.comments]
      .some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    return (statusFilter === "All" || i.status === statusFilter) && matchSearch
      && (!clientFilter || i.account_id === Number(clientFilter))
      && (!invoicingFilter || invoicingOf(invoiceById[i.invoice_id]) === invoicingFilter);
  });

  const openNew = () => {
    setForm({ ...emptyForm(clientFilter), triam_entity: clientEntities(accountById[clientFilter])[0] || "" });
    setModal("new");
  };
  const openEdit = (i) => { setForm(toForm(i)); setModal("edit"); };

  const invoice = form.invoice_id ? invoiceById[form.invoice_id] : null;
  const withAccountant = !!invoice && invoice.status !== "Cancelled";
  // A dropped request, or any request a read-only user opens, is shown as it is. A completed one stays
  // editable: the client's payment may arrive after the work is done.
  const requestLocked = readOnly || (modal === "edit" && instructions.find((x) => x.id === form.id)?.status === "Dropped");
  // The Accountant working an invoice sees their own buttons, not the RM's.
  const accountantView = withAccountant && accountant && !readOnly;

  const problem = () => {
    if (!form.account_id) return "Choose the client for this service request";
    if (!form.instruction_type) return "Choose the request type";
    if (form.instruction_type === "Other" && !form.other_description?.trim()) return "Describe the request (up to 50 characters)";
    return null;
  };

  // Save, and with submit=true send the request to the Accountant's queue.
  const save = async (submit = false) => {
    const p = problem();
    if (p) return toast.error(p);
    if (submit && !(Number(form.charge_amount) > 0)) return toast.error("Enter the charge to the client before submitting");
    if (submit && form.service_provider_involved && !form.service_provider_name?.trim()) return toast.error("Enter the name of the service provider");
    setBusy(true);
    try {
      const payload = cleanPayload({ ...form, status: form.status || firstOpenStatus(formOpts) });
      let id = form.id;
      if (modal === "new") {
        id = (await instructionsApi.create({ ...payload, account_id: Number(payload.account_id) })).id;
      } else {
        const patch = Object.fromEntries(Object.entries(payload).filter(([k]) => !SERVER_FIELDS.includes(k)));
        await instructionsApi.update(id, patch);
      }
      if (submit) {
        await instructionsApi.submit(id);
        toast.success("Submitted. It is now in the Accountant's queue.");
      } else {
        toast.success(modal === "new" ? "Service request created" : "Service request saved");
      }
      setModal(null); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
      load();
    } finally { setBusy(false); }
  };

  const quickSetStatus = async (i, status) => {
    try { await instructionsApi.update(i.id, { status }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  // Service requests are never deleted: they are cancelled with a reason and stay on record.
  const cancelRequest = async (i) => {
    const reason = await reasonDialog({ title: "Cancel service request", confirmLabel: "Cancel request",
      message: `${requestLabel(i)} will be marked Dropped and kept on record.` });
    if (!reason) return;
    try { await instructionsApi.cancel(i.id, reason); toast.success("Service request cancelled"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Cancel failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const counts = allStatuses.reduce((acc, s) => ({ ...acc, [s]: instructions.filter((i) => i.status === s).length }), {});
  const invoicingCounts = instructions.reduce((acc, i) => ({ ...acc, [invoicingOf(invoiceById[i.invoice_id])]: (acc[invoicingOf(invoiceById[i.invoice_id])] || 0) + 1 }), {});
  const client = accountById[form.account_id];

  return (
    <div className="space-y-4">
      <PageHeader title="Service Requests"
        subtitle={<>{filtered.length} of {instructions.length} service requests</>}
        actions={!readOnly &&
          <button onClick={openNew} className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 hover:opacity-90" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={14} /> New Service Request
          </button>
        } />

      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-48">
          <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search client, request type, comments..."
            className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-brand-400" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-brand-400">
          <option value="All">All statuses ({instructions.length})</option>
          {allStatuses.map((s) => <option key={s} value={s}>{s} ({counts[s] || 0})</option>)}
        </select>
        <select aria-label="Invoicing" value={invoicingFilter} onChange={(e) => setInvoicingFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-brand-400">
          {Object.entries(INVOICING).map(([k, label]) => <option key={k} value={k}>{label}{k ? ` (${invoicingCounts[k] || 0})` : ""}</option>)}
        </select>
        <select value={clientFilter} onChange={(e) => setClientFilter(e.target.value)}
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-brand-400">
          <option value="">All clients</option>
          {accounts.map((a) => <option key={a.id} value={a.id}>{a.company_name}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Client</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Triam Entity</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Request Type</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Status</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Received</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Completed</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Charge</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Invoice</th>
              <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={9} className="py-8 text-center text-sm text-gray-400">No service requests match this filter.</td></tr>
            )}
            {filtered.map((i) => {
              const acc = accountById[i.account_id];
              const inv = invoiceById[i.invoice_id];
              const stage = invoicingOf(inv);
              return (
                <tr key={i.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 px-4 text-xs">
                    <div className="font-medium text-gray-800">{acc?.company_name || "—"}</div>
                    <div className="text-gray-400 font-mono">{acc?.client_id || ""}</div>
                  </td>
                  <td className="py-3 px-4 text-xs text-gray-600">{i.triam_entity || "—"}</td>
                  <td className="py-3 px-4 text-xs text-gray-600">{requestLabel(i)}</td>
                  <td className="py-3 px-4">
                    {CLOSED.includes(i.status) || readOnly ? (
                      <span className={`text-xs ${i.status === "Dropped" ? "text-gray-400" : i.status === "Completed" ? "text-emerald-700" : "text-gray-600"}`} title={i.cancel_reason || ""}>{i.status}</span>
                    ) : (
                      <select value={i.status} onChange={(e) => quickSetStatus(i, e.target.value)}
                        className="text-xs border-0 bg-transparent focus:outline-none cursor-pointer max-w-[11rem]">
                        {pickableStatuses(optionsFor(i.triam_entity), i.status).map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="py-3 px-4 text-xs text-gray-500">{fmtDate(i.date_received) || "—"}</td>
                  <td className="py-3 px-4 text-xs text-gray-500">{fmtDate(i.date_completed) || "—"}</td>
                  <td className="py-3 px-4 text-xs text-right text-gray-600 whitespace-nowrap">{i.charge_amount != null ? fmtMoney(i.charge_currency, i.charge_amount) : "—"}</td>
                  <td className="py-3 px-4 text-xs">
                    {stage === "none" ? <span className="text-gray-400">—</span>
                      : stage === "accountant" ? <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700">With the Accountant</span>
                        : <span className="text-gray-600">{inv.invoice_number || `#${inv.id}`} <span className="text-gray-400">({inv.status})</span></span>}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1">
                      <button onClick={() => openEdit(i)} title={accountant && stage === "accountant" ? "Open to invoice" : "Open"}
                        aria-label={`Open ${requestLabel(i)}`}
                        className={`p-1.5 rounded hover:bg-brand-50 ${accountant && stage === "accountant" ? "text-amber-600" : "text-gray-400"} hover:text-brand-600`}>
                        <Icon name={readOnly || i.status === "Dropped" ? "view" : "edit"} size={14} />
                      </button>
                      {!readOnly && !CLOSED.includes(i.status) && (
                        <button onClick={() => cancelRequest(i)} title="Cancel request" className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                          <Icon name="close" size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {modal && (
        <Modal title={modal === "new" ? "New Service Request" : requestLocked ? "Service Request" : "Edit Service Request"} onClose={() => setModal(null)}>
          {/* The Accountant reads the RM's part and fills only their own section. */}
          <fieldset disabled={requestLocked || accountantView || busy} className="min-w-0">
            <div className="grid grid-cols-2 gap-x-4">
              <Field label="Triam entity" required>
                <Select value={form.triam_entity || ""} disabled={modal === "edit"} onChange={(e) => chooseEntity(e.target.value)}>
                  <option value="">— choose —</option>
                  {[...new Set([...activeEntities, ...(form.triam_entity ? [form.triam_entity] : [])])]
                    .map((e) => <option key={e} value={e}>{triamEntities.labelOf(e) || e}</option>)}
                </Select>
              </Field>
              <Field label="Client" required>
                <Select value={form.account_id || ""} disabled={modal === "edit" || !form.triam_entity} onChange={(e) => set("account_id")(e.target.value)}>
                  <option value="">{form.triam_entity ? (entityClients.length ? "— choose client —" : "— no clients approved by Compliance for this entity —") : "— choose the entity first —"}</option>
                  {entityClients.map((a) => <option key={a.id} value={a.id}>{a.client_id ? `${a.client_id} – ` : ""}{a.company_name}</option>)}
                </Select>
              </Field>
              <Field label="Request Type" required>
                <Select value={form.instruction_type || ""} disabled={!form.triam_entity}
                  onChange={(e) => setForm((p) => ({ ...p, instruction_type: e.target.value, other_description: e.target.value === "Other" ? p.other_description : "" }))}>
                  <option value="">{form.triam_entity ? "— choose —" : "— choose the entity first —"}</option>
                  {[...new Set([...formOpts.types, ...(form.instruction_type ? [form.instruction_type] : [])])]
                    .map((t) => <option key={t} value={t}>{requestTypes.labelOf(t) || t}</option>)}
                </Select>
              </Field>
              {form.instruction_type === "Other" ? (
                <Field label="Describe the request" required>
                  <Input maxLength={50} value={form.other_description || ""} placeholder="Up to 50 characters"
                    onChange={(e) => set("other_description")(e.target.value)} />
                </Field>
              ) : (
                <Field label="Client's VAT No.">
                  <Input value={client?.trn_vat_number || ""} readOnly disabled placeholder={client ? "Not on the client profile" : "Choose the client"} />
                </Field>
              )}
              <Field label="Status">
                <Select value={form.status || firstOpenStatus(formOpts)} onChange={(e) => set("status")(e.target.value)}>
                  {pickableStatuses(formOpts, form.status).map((s) => <option key={s}>{s}</option>)}
                </Select>
              </Field>
              <Field label="Charge to the client (excluding VAT)">
                <MoneyInput label="Charge to the client" currency={form.charge_currency} amount={form.charge_amount}
                  disabled={withAccountant} onCurrency={setChargeCurrency} onAmount={set("charge_amount")} />
              </Field>
              <Field label="Date Received">
                <DateInput value={form.date_received || ""} onChange={(e) => set("date_received")(e.target.value)} />
              </Field>
              <Field label="Date Completed">
                <DateInput value={form.date_completed || ""} onChange={(e) => set("date_completed")(e.target.value)} />
              </Field>
              <Field label="Amount paid by the client">
                <MoneyInput label="Amount paid by the client" currency={form.amount_paid_currency} amount={form.amount_paid}
                  onCurrency={set("amount_paid_currency")} onAmount={set("amount_paid")} />
              </Field>
              <Field label="Date amount received by Triam">
                <DateInput value={form.payment_received_date || ""} onChange={(e) => set("payment_received_date")(e.target.value)} />
              </Field>
              {form.instruction_type === "Other" && (
                <Field label="Client's VAT No.">
                  <Input value={client?.trn_vat_number || ""} readOnly disabled placeholder={client ? "Not on the client profile" : "Choose the client"} />
                </Field>
              )}
            </div>

            <div className="border-t border-gray-100 pt-3 mt-1">
              <Field label="Is a service provider involved?">
                <div className="flex gap-4 text-sm">
                  {[["Yes", true], ["No", false]].map(([label, value]) => (
                    <label key={label} className="flex items-center gap-1.5">
                      <input type="radio" name="service_provider_involved" checked={form.service_provider_involved === value}
                        onChange={() => set("service_provider_involved")(value)} /> {label}
                    </label>
                  ))}
                </div>
              </Field>
              {form.service_provider_involved && (
                <div className="grid grid-cols-2 gap-x-4">
                  <Field label="Name of the service provider" required>
                    <Input maxLength={150} value={form.service_provider_name || ""} onChange={(e) => set("service_provider_name")(e.target.value)} />
                  </Field>
                  <Field label="Amount payable to the service provider">
                    <MoneyInput label="Amount payable to the service provider" currency={form.service_provider_currency} amount={form.service_provider_amount}
                      onCurrency={set("service_provider_currency")} onAmount={set("service_provider_amount")} />
                  </Field>
                </div>
              )}
            </div>
            <Field label="Comments"><Textarea value={form.comments || ""} onChange={(e) => set("comments")(e.target.value)} /></Field>
          </fieldset>

          {withAccountant && form.submitted_at && (
            <p className="text-xs text-gray-500 mb-2">Submitted to the Accountant on {fmtDate(form.submitted_at)}. The charge can be changed only if the Accountant cancels the invoice.</p>
          )}

          {!requestLocked && !accountantView && (
            <div className="flex justify-end gap-3 mt-2">
              <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
              <button onClick={() => save(false)} disabled={busy} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60">Save</button>
              {!withAccountant && (
                <button onClick={() => save(true)} disabled={busy} title="Saves and sends the request to the Accountant's queue for invoicing"
                  className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-60" style={{ background: "#1a3a5c" }}>{busy ? "Sending…" : "Submit"}</button>
              )}
            </div>
          )}

          {withAccountant && (
            <AccountantSection invoice={invoice} canManage={accountant && !readOnly} onDone={() => { setModal(null); load(); }} />
          )}
          {(requestLocked || (accountantView && !WITH_ACCOUNTANT.includes(invoice.status))) && (
            <div className="flex justify-end mt-3">
              <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Close</button>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}

/** Triam's Invoice Box template: the Accountant's part of the window. Save keeps the details; Send to RM
 *  raises the invoice (the file is needed) and tells the RM it is ready. */
function AccountantSection({ invoice, canManage, onDone }) {
  const open = WITH_ACCOUNTANT.includes(invoice.status);
  const [form, setForm] = useState({
    invoice_number: invoice.invoice_number || "", invoice_date: invoice.raised_date || new Date().toISOString().slice(0, 10),
    currency: invoice.currency || "AED", amount: invoice.amount ?? "",
  });
  const [file, setFile] = useState(null);
  const [files, setFiles] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { invoicesApi.attachments(invoice.id).then((d) => setFiles(d.filter((x) => x.category === "Invoice"))).catch(() => setFiles([])); }, [invoice.id]);
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const saveDetails = async () => {
    setBusy(true);
    try {
      if (file) await invoicesApi.attach(invoice.id, file, "Invoice");
      await invoicesApi.update(invoice.id, { invoice_number: form.invoice_number.trim() || null, raised_date: form.invoice_date || null,
        currency: form.currency, amount: form.amount === "" ? undefined : form.amount });
      toast.success("Invoice details saved");
      onDone();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save the invoice details"); } finally { setBusy(false); }
  };
  const sendToRm = async () => {
    if (!form.invoice_number.trim() || !form.invoice_date || form.amount === "") return toast.error("Enter the invoice number, date and amount");
    if (!file && !(files || []).length) return toast.error("Upload the invoice");
    setBusy(true);
    try {
      if (file) await invoicesApi.attach(invoice.id, file, "Invoice");
      await invoicesApi.raise(invoice.id, { invoice_number: form.invoice_number.trim(), invoice_date: form.invoice_date,
        currency: form.currency, amount: form.amount, due_date: null });
      toast.success("Invoice sent to the RM");
      onDone();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not send the invoice"); } finally { setBusy(false); }
  };

  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50/40 p-3">
      <div className="text-xs font-semibold text-gray-700 mb-2 uppercase tracking-wide">To be filled by the Accountant</div>
      {open && !canManage ? (
        <p className="text-xs text-gray-600">With the Accountant since {fmtDate(invoice.requested_at) || "—"}: {fmtMoney(invoice.currency, invoice.amount)} to invoice.</p>
      ) : (
        <fieldset disabled={!open || !canManage || busy} className="min-w-0">
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Invoice No." required><Input maxLength={50} value={form.invoice_number} onChange={(e) => set("invoice_number")(e.target.value)} /></Field>
            <Field label="Date of Invoice" required><DateInput value={form.invoice_date} onChange={(e) => set("invoice_date")(e.target.value)} /></Field>
            <Field label="Invoice Amount" required>
              <MoneyInput label="Invoice Amount" currency={form.currency} amount={form.amount} onCurrency={set("currency")} onAmount={set("amount")} />
            </Field>
            <Field label="Invoice" required={open}>
              {(files || []).map((d) => (
                <button key={d.id} type="button" onClick={() => documentsApi.download(d.id, d.filename)} className="flex items-center gap-1.5 text-xs text-brand-600 hover:underline">
                  <Icon name="download" size={12} />{d.filename}
                </button>
              ))}
              {open && canManage && (
                <input type="file" aria-label="Upload the invoice" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.bmp" onChange={(e) => setFile(e.target.files[0] || null)}
                  className="mt-1 text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
              )}
            </Field>
          </div>
        </fieldset>
      )}
      {!open && <p className="text-xs text-gray-600">Invoice {invoice.invoice_number} sent to the RM ({invoice.status}).</p>}
      {open && canManage && (
        <div className="flex justify-end gap-3 mt-2">
          <button onClick={onDone} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
          <button onClick={saveDetails} disabled={busy} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-60">Save</button>
          <button onClick={sendToRm} disabled={busy} className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-60" style={{ background: "#1a3a5c" }}>{busy ? "Sending…" : "Send to RM"}</button>
        </div>
      )}
    </div>
  );
}
