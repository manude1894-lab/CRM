import React, { useEffect, useMemo, useState } from "react";
import { prospectsApi, usersApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, PageHeader, DateInput } from "../components/ui";
import DuplicateWarning from "../components/DuplicateWarning";
import { PROSPECT_STATUS_OPTIONS, CASE_SOURCE_OPTIONS, JURISDICTION_OPTIONS, SERVICE_TYPE_OPTIONS, fmtFull, fmtDate } from "../utils/constants";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";
import { useAuthStore } from "../store/auth";
import { wordCount } from "../components/accounts/WorkflowBar";

const empty = {
  company_name: "", contact_name: "", contact_email: "", contact_phone: "",
  source: "Referral", owner_id: "", status: "New", proposal_sent_date: "",
  proposal_amount: "", expected_close_date: "", next_follow_up_date: "",
  lost_reason: "", notes: "",
};

/**
 * Triam BRD mark-up §4A — every new client starts here. The Prospecting Team Coordinator assigns the RM
 * (with optional Assignor's comments) or an RM takes an unassigned prospect; the RM then creates the
 * client from the prospect, whose Prospect ID is the client's temporary ID until Compliance approves.
 */
export default function ProspectsPage({ onNavigate } = {}) {
  const [items, setItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [convertProspect, setConvertProspect] = useState(null);
  const [convertForm, setConvertForm] = useState({ jurisdiction: "BVI", service_type: "Company Formation", rm_id: "" });
  const [assign, setAssign] = useState(null); // { prospect, rm_id, comments }
  const me = useAuthStore((s) => s.user);
  const coordinator = useAuthStore((s) => s.can("prospect.assign"));

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [ps, us] = await Promise.all([prospectsApi.list(), usersApi.list()]);
      setItems(ps || []);
      setUsers(us || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load prospects");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const userById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users]);

  const openNew = () => { setForm({ ...empty }); setModal(true); };
  const openEdit = (p) => {
    setForm({
      ...p, owner_id: p.owner_id ?? "", proposal_sent_date: p.proposal_sent_date || "",
      proposal_amount: p.proposal_amount ?? "", expected_close_date: p.expected_close_date || "",
      next_follow_up_date: p.next_follow_up_date || "",
    });
    setModal(true);
  };

  const save = async () => {
    const payload = {
      ...form,
      owner_id: form.owner_id ? Number(form.owner_id) : null,
      proposal_amount: form.proposal_amount || null,
      proposal_sent_date: form.proposal_sent_date || null,
      expected_close_date: form.expected_close_date || null,
      next_follow_up_date: form.next_follow_up_date || null,
      lost_reason: form.lost_reason || null,
    };
    try {
      if (form.id) {
        const { id, prospect_uid, converted_case_id, converted_account_id, assigned_by_id, assigned_by_name, assigned_at,
          assignor_comments, owner_name, created_at, updated_at, ...patch } = payload;
        if (!coordinator) delete patch.owner_id;  // assignment goes through Assign
        await prospectsApi.update(form.id, patch);
      } else {
        await prospectsApi.create(payload);
      }
      setModal(false); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };

  const move = async (p, status) => {
    try { await prospectsApi.update(p.id, { status }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (p) => {
    if (!(await confirmDialog(`Delete prospect "${p.company_name}"?`))) return;
    try { await prospectsApi.delete(p.id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const doAssign = async () => {
    try {
      await prospectsApi.assign(assign.prospect.id, { rm_id: Number(assign.rm_id), comments: assign.comments || null });
      toast.success("Prospect assigned");
      setAssign(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Assignment failed"); }
  };
  const createClient = (p) => onNavigate?.({ page: "accounts", prospectId: p.id });

  const openConvert = (p) => {
    setConvertForm({ jurisdiction: "BVI", service_type: "Company Formation", rm_id: p.owner_id || "" });
    setConvertProspect(p);
  };

  const doConvert = async () => {
    try {
      await prospectsApi.convert(convertProspect.id, {
        jurisdiction: convertForm.jurisdiction,
        service_type: convertForm.service_type,
        rm_id: convertForm.rm_id ? Number(convertForm.rm_id) : null,
      });
      setConvertProspect(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Convert failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <PageHeader title="Prospects"
        subtitle={<>{items.length} tracked leads / proposals — not yet onboarded clients</>}
        actions={<>
<button onClick={openNew} className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 hover:opacity-90" style={{ background: "#1a3a5c" }}>
          <Icon name="plus" size={14} /> Add Prospect
        </button>
        </>} />

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 overflow-x-auto">
        {PROSPECT_STATUS_OPTIONS.map((col) => {
          const colItems = items.filter((p) => p.status === col);
          return (
            <div key={col} className="min-w-[220px]">
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-xs font-semibold text-gray-700">{col}</span>
                <span className="text-xs text-gray-400 bg-gray-100 rounded-full px-2 py-0.5">{colItems.length}</span>
              </div>
              <div className="space-y-2 min-h-16">
                {colItems.map((p) => (
                  <div key={p.id} className="bg-white border border-gray-100 rounded-xl p-3 shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <button onClick={() => openEdit(p)} className="text-xs font-semibold text-gray-800 text-left hover:text-brand-600">{p.company_name}</button>
                    </div>
                    <div className="text-[11px] text-gray-400 mt-1">{p.prospect_uid}</div>
                    {p.contact_name && <div className="text-xs text-gray-500 mt-1">{p.contact_name}</div>}
                    <div className="text-[11px] text-gray-400 mt-1 space-y-0.5">
                      {p.owner_id
                        ? <div>RM: <span className="text-gray-600">{p.owner_name || userById[p.owner_id]?.name || `User #${p.owner_id}`}</span></div>
                        : <div className="text-amber-700 font-medium">Not yet assigned</div>}
                      {p.assignor_comments && <div className="italic line-clamp-2" title={p.assignor_comments}>“{p.assignor_comments}”</div>}
                      {p.proposal_amount && <div>{fmtFull(p.proposal_amount)}</div>}
                      {p.next_follow_up_date && <div>Follow up {fmtDate(p.next_follow_up_date)}</div>}
                    </div>
                    {p.converted_account_id && (
                      <button onClick={() => onNavigate?.({ page: "accounts", accountId: p.converted_account_id })}
                        className="mt-1 text-[11px] text-emerald-700 hover:underline">Client created — open</button>
                    )}
                    {p.converted_case_id && !p.converted_account_id && <div className="mt-1"><Badge text="Converted" /></div>}
                    <div className="flex items-center gap-1 mt-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
                      {!p.converted_account_id && coordinator && (
                        <button onClick={() => setAssign({ prospect: p, rm_id: p.owner_id || "", comments: p.assignor_comments || "" })}
                          className="text-xs px-2 py-0.5 rounded border border-brand-200 text-brand-700 hover:bg-brand-50">{p.owner_id ? "Reassign" : "Assign"}</button>
                      )}
                      {!p.converted_account_id && !coordinator && !p.owner_id && (
                        <button onClick={() => setAssign({ prospect: p, rm_id: me?.id, comments: "", self: true })}
                          className="text-xs px-2 py-0.5 rounded border border-brand-200 text-brand-700 hover:bg-brand-50">Assign to me</button>
                      )}
                      {!p.converted_account_id && p.owner_id && p.status !== "Lost" && (coordinator || p.owner_id === me?.id || me?.role === "admin") && (
                        <button onClick={() => createClient(p)} className="text-xs px-2 py-0.5 rounded border border-emerald-300 text-emerald-700 hover:bg-emerald-50">Create client</button>
                      )}
                      {!p.converted_case_id && !p.converted_account_id && PROSPECT_STATUS_OPTIONS.filter((s) => s !== p.status).map((s) => (
                        <button key={s} onClick={() => move(p, s)} className="text-xs px-2 py-0.5 rounded border border-gray-200 text-gray-500 hover:bg-gray-50">{s}</button>
                      ))}
                      <button onClick={() => remove(p)} className="ml-auto p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                        <Icon name="del" size={12} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {modal && (
        <Modal title={form.id ? "Edit Prospect" : "New Prospect"} onClose={() => setModal(false)}>
          <Field label="Company Name" required><Input value={form.company_name || ""} onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))} /></Field>
          <DuplicateWarning name={form.company_name} excludeId={form.id} checkFn={prospectsApi.checkDuplicate} active={!form.id} />
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Contact Name"><Input value={form.contact_name || ""} onChange={(e) => setForm((p) => ({ ...p, contact_name: e.target.value }))} /></Field>
            <Field label="Contact Email"><Input value={form.contact_email || ""} onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))} /></Field>
            <Field label="Contact Phone"><Input value={form.contact_phone || ""} onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))} /></Field>
            <Field label="Source">
              <Select value={form.source || "Referral"} onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))}>
                {CASE_SOURCE_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            {coordinator ? (
              <Field label="Assigned RM">
                <Select value={form.owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, owner_id: e.target.value }))}>
                  <option value="">— Not yet assigned —</option>
                  {users.filter((u) => u.role === "rm" && u.is_active !== false).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                </Select>
              </Field>
            ) : (
              <Field label="Assigned RM"><Input disabled value={form.id ? (form.owner_name || "Not yet assigned") : `${me?.name || "You"} (you)`} /></Field>
            )}
            <Field label="Status">
              <Select value={form.status || "New"} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {PROSPECT_STATUS_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            <Field label="Proposal Sent Date"><DateInput value={form.proposal_sent_date || ""} onChange={(e) => setForm((p) => ({ ...p, proposal_sent_date: e.target.value }))} /></Field>
            <Field label="Proposal Amount"><Input type="number" min="0" step="0.01" value={form.proposal_amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, proposal_amount: e.target.value }))} /></Field>
            <Field label="Expected Close Date"><DateInput value={form.expected_close_date || ""} onChange={(e) => setForm((p) => ({ ...p, expected_close_date: e.target.value }))} /></Field>
            <Field label="Next Follow-up Date"><DateInput value={form.next_follow_up_date || ""} onChange={(e) => setForm((p) => ({ ...p, next_follow_up_date: e.target.value }))} /></Field>
          </div>
          {form.status === "Lost" && (
            <Field label="Lost Reason"><Textarea value={form.lost_reason || ""} onChange={(e) => setForm((p) => ({ ...p, lost_reason: e.target.value }))} /></Field>
          )}
          <Field label="Notes"><Textarea value={form.notes || ""} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}

      {assign && (
        <Modal title={`${assign.self ? "Assign to me" : "Assign RM"} — ${assign.prospect.company_name}`} onClose={() => setAssign(null)}>
          <div className="text-xs text-gray-500 mb-3">Prospect <span className="font-mono">{assign.prospect.prospect_uid}</span></div>
          {!assign.self && (
            <Field label="Relationship Manager" required>
              <Select value={assign.rm_id || ""} onChange={(e) => setAssign((a) => ({ ...a, rm_id: e.target.value }))}>
                <option value="">— choose —</option>
                {users.filter((u) => u.role === "rm" && u.is_active !== false).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
          )}
          <Field label="Assignor's comments (optional)">
            <Textarea rows={4} value={assign.comments} onChange={(e) => setAssign((a) => ({ ...a, comments: e.target.value }))} maxLength={4000} />
            <div className={`text-[11px] text-right mt-0.5 ${wordCount(assign.comments) > 250 ? "text-red-600" : "text-gray-400"}`}>{wordCount(assign.comments)} / 250 words</div>
          </Field>
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setAssign(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={doAssign} disabled={!assign.rm_id || wordCount(assign.comments) > 250}
              className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50" style={{ background: "#1a3a5c" }}>Assign</button>
          </div>
        </Modal>
      )}

      {convertProspect && (
        <Modal title={`Convert "${convertProspect.company_name}" to a Case`} onClose={() => setConvertProspect(null)}>
          <p className="text-sm text-gray-600 mb-3">This creates a new onboarding Case from this prospect. The prospect will be marked Won and linked to the new case.</p>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Jurisdiction">
              <Select value={convertForm.jurisdiction} onChange={(e) => setConvertForm((p) => ({ ...p, jurisdiction: e.target.value }))}>
                {JURISDICTION_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            <Field label="Service Type">
              <Select value={convertForm.service_type} onChange={(e) => setConvertForm((p) => ({ ...p, service_type: e.target.value }))}>
                {SERVICE_TYPE_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            <Field label="Relationship Manager">
              <Select value={convertForm.rm_id || ""} onChange={(e) => setConvertForm((p) => ({ ...p, rm_id: e.target.value }))}>
                <option value="">— Unassigned —</option>
                {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setConvertProspect(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={doConvert} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Convert</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
