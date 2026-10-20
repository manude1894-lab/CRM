import React, { useEffect, useMemo, useState } from "react";
import { instructionsApi, invoicesApi, accountsApi } from "../api/endpoints";
import { useMasters } from "../hooks/useMasters";
import { Icon, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, PageHeader, DateInput } from "../components/ui";
import { fmtFull, fmtDate } from "../utils/constants";
import { useRequestOptions, pickableStatuses, firstOpenStatus, requestLabel, clientEntities } from "../hooks/useRequestOptions";
import { toast } from "../store/toast";
import { reasonDialog } from "../store/confirm";

// BRD §15 — service requests on approved clients. Request types and statuses follow the Triam entity
// handling the request (Triam's "Service Requests - Triam Entities" list, kept as master data).
const SERVICEABLE = ["Approved", "Active", "Inactive", "Marked for Exit"];
const CLOSED = ["Dropped", "Completed"];

const emptyForm = (accountId) => ({
  account_id: accountId || "",
  triam_entity: "",
  instruction_type: "",
  other_description: "",
  status: "",
  date_received: new Date().toISOString().split("T")[0],
  date_completed: "",
  charge_amount: "",
  invoice_id: "",
  comments: "",
});

// Blank strings go as null so optional date / number fields don't fail validation.
const cleanPayload = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, v === "" ? null : v]));

export default function InstructionsPage() {
  const [instructions, setInstructions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [clientFilter, setClientFilter] = useState("");
  const requestTypes = useMasters("service_request_type", []);
  const triamEntities = useMasters("triam_entity", []);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

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
  const formEntities = (() => {
    const served = clientEntities(accountById[form.account_id]);
    return served.length ? served : triamEntities.items.map((e) => e.code);
  })();
  const allStatuses = [...new Set(instructions.map((i) => i.status))];
  // Picking the client picks its anchor entity; a new entity resets the type and status to that entity's lists.
  const chooseClient = (accountId) => setForm((p) => ({ ...p, account_id: accountId,
    triam_entity: clientEntities(accountById[accountId])[0] || "", instruction_type: "", other_description: "", status: "", invoice_id: "" }));
  const chooseEntity = (entity) => setForm((p) => ({ ...p, triam_entity: entity, instruction_type: "", other_description: "", status: "" }));
  const clientInvoices = invoices.filter((inv) => inv.account_id === Number(form.account_id) && inv.status !== "Cancelled");

  const filtered = instructions.filter((i) => {
    const acc = accountById[i.account_id];
    const matchSearch = search === "" || [acc?.company_name, acc?.client_id, i.instruction_type, i.other_description, i.comments]
      .some((v) => v?.toLowerCase().includes(search.toLowerCase()));
    return (statusFilter === "All" || i.status === statusFilter) && matchSearch
      && (!clientFilter || i.account_id === Number(clientFilter));
  });

  const openNew = () => {
    setForm({ ...emptyForm(clientFilter), triam_entity: clientEntities(accountById[clientFilter])[0] || "" });
    setModal("new");
  };
  const openEdit = (i) => {
    setForm({ ...i, triam_entity: i.triam_entity || "", other_description: i.other_description || "",
      charge_amount: i.charge_amount ?? "", invoice_id: i.invoice_id || "" });
    setModal("edit");
  };

  const save = async () => {
    if (!form.account_id) return toast.error("Choose the client for this service request");
    if (!form.instruction_type) return toast.error("Choose the request type");
    if (form.instruction_type === "Other" && !form.other_description?.trim()) return toast.error("Describe the request (up to 50 characters)");
    try {
      const payload = cleanPayload({ ...form, status: form.status || firstOpenStatus(formOpts) });
      if (payload.invoice_id != null) payload.invoice_id = Number(payload.invoice_id);
      if (modal === "new") {
        await instructionsApi.create({ ...payload, account_id: Number(payload.account_id) });
        toast.success("Service request created");
      } else {
        const { id, account_id, created_at, updated_at, cancel_reason, ...patch } = payload;
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

  return (
    <div className="space-y-4">
      <PageHeader title="Service Requests"
        subtitle={<>{filtered.length} of {instructions.length} service requests</>}
        actions={
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
              return (
                <tr key={i.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 px-4 text-xs">
                    <div className="font-medium text-gray-800">{acc?.company_name || "—"}</div>
                    <div className="text-gray-400 font-mono">{acc?.client_id || ""}</div>
                  </td>
                  <td className="py-3 px-4 text-xs text-gray-600">{i.triam_entity || "—"}</td>
                  <td className="py-3 px-4 text-xs text-gray-600">{requestLabel(i)}</td>
                  <td className="py-3 px-4">
                    {CLOSED.includes(i.status) ? (
                      <span className={`text-xs ${i.status === "Dropped" ? "text-gray-400" : "text-emerald-700"}`} title={i.cancel_reason || ""}>{i.status}</span>
                    ) : (
                      <select value={i.status} onChange={(e) => quickSetStatus(i, e.target.value)}
                        className="text-xs border-0 bg-transparent focus:outline-none cursor-pointer max-w-[11rem]">
                        {pickableStatuses(optionsFor(i.triam_entity), i.status).map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    )}
                  </td>
                  <td className="py-3 px-4 text-xs text-gray-500">{fmtDate(i.date_received) || "—"}</td>
                  <td className="py-3 px-4 text-xs text-gray-500">{fmtDate(i.date_completed) || "—"}</td>
                  <td className="py-3 px-4 text-xs text-right text-gray-600">{i.charge_amount != null ? fmtFull(i.charge_amount) : "—"}</td>
                  <td className="py-3 px-4 text-xs text-gray-500">{inv ? `${inv.invoice_number || `#${inv.id}`} (${inv.status})` : "—"}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1">
                      {!CLOSED.includes(i.status) && (<>
                        <button onClick={() => openEdit(i)} className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600">
                          <Icon name="edit" size={14} />
                        </button>
                        <button onClick={() => cancelRequest(i)} title="Cancel request" className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                          <Icon name="close" size={14} />
                        </button>
                      </>)}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {modal && (
        <Modal title={modal === "new" ? "New Service Request" : "Edit Service Request"} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Client" required>
              <Select value={form.account_id || ""} disabled={modal === "edit"} onChange={(e) => chooseClient(e.target.value)}>
                <option value="">— choose client —</option>
                {accounts.filter((a) => modal === "edit" || SERVICEABLE.includes(a.profile_status))
                  .map((a) => <option key={a.id} value={a.id}>{a.client_id ? `${a.client_id} – ` : ""}{a.company_name}</option>)}
              </Select>
            </Field>
            <Field label="Triam entity" required>
              <Select value={form.triam_entity || ""} onChange={(e) => chooseEntity(e.target.value)}>
                <option value="">— choose —</option>
                {formEntities.map((e) => <option key={e} value={e}>{triamEntities.labelOf(e) || e}</option>)}
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
                  onChange={(e) => setForm((p) => ({ ...p, other_description: e.target.value }))} />
              </Field>
            ) : <div />}
            <Field label="Status">
              <Select value={form.status || firstOpenStatus(formOpts)} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {pickableStatuses(formOpts, form.status).map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Charge to the client">
              <Input type="number" min="0" step="0.01" value={form.charge_amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, charge_amount: e.target.value }))} />
            </Field>
            <Field label="Date Received">
              <DateInput value={form.date_received || ""} onChange={(e) => setForm((p) => ({ ...p, date_received: e.target.value }))} />
            </Field>
            <Field label="Date Completed">
              <DateInput value={form.date_completed || ""} onChange={(e) => setForm((p) => ({ ...p, date_completed: e.target.value }))} />
            </Field>
            <Field label="Invoice">
              <Select value={form.invoice_id || ""} disabled={!form.account_id} onChange={(e) => setForm((p) => ({ ...p, invoice_id: e.target.value }))}>
                <option value="">— none —</option>
                {clientInvoices.map((inv) => <option key={inv.id} value={inv.id}>{inv.invoice_number || `Invoice #${inv.id}`} ({inv.status})</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Comments"><Textarea value={form.comments || ""} onChange={(e) => setForm((p) => ({ ...p, comments: e.target.value }))} /></Field>
          <p className="text-[11px] text-gray-400 -mt-2 mb-3">When a request with a charge is completed, Accounts receive an invoice instruction automatically.</p>

          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
