import React, { useEffect, useMemo, useState } from "react";
import { prospectsApi, usersApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, PageHeader, DateInput, SelectWithOther } from "../components/ui";
import DuplicateWarning from "../components/DuplicateWarning";
import { PROSPECT_STATUS_OPTIONS, PROSPECT_SOURCE_OPTIONS, isRelationshipManager } from "../utils/constants";
import { toast } from "../store/toast";
import { useAuthStore } from "../store/auth";
import { wordCount } from "../components/accounts/WorkflowBar";

const empty = {
  company_name: "", contact_name: "", contact_email: "", contact_phone: "",
  source: "Referral", owner_id: "", status: "New", proposal_sent_date: "",
  lost_reason: "", notes: "", assignor_comments: "",
};
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * BRD §4A — every new client starts here. The Prospecting Team Coordinator assigns the RM
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
    setForm({ ...p, owner_id: p.owner_id ?? "", proposal_sent_date: p.proposal_sent_date || "", assignor_comments: p.assignor_comments || "" });
    setModal(true);
  };

  // Cancel / Save / Submit (Triam input 19-10-2026): Save keeps the prospect without sending it;
  // Submit also sends it to the named RM (BRD §4A assignment: notified, with the assignor's comments).
  const save = async (submit = false) => {
    if (!form.company_name?.trim()) return toast.error("Enter the prospect's name");
    if (form.contact_email && !EMAIL_RE.test(form.contact_email.trim())) return toast.error("Enter the contact email as name@domain.com");
    const rmId = coordinator ? (form.owner_id ? Number(form.owner_id) : null) : me?.id;
    if (submit && !rmId) return toast.error("Choose the RM to submit the prospect to");
    if (submit && wordCount(form.assignor_comments) > 250) return toast.error("Assignor's comments can be at most 250 words");
    const { id, prospect_uid, converted_account_id, assigned_by_id, assigned_by_name, assigned_at, assignor_comments,
      owner_name, created_at, updated_at, owner_id, ...fields } = form;
    const payload = {
      ...fields,
      contact_email: form.contact_email?.trim() || null,
      proposal_sent_date: form.proposal_sent_date || null,
      lost_reason: form.lost_reason || null,
    };
    try {
      const saved = form.id ? await prospectsApi.update(form.id, payload) : await prospectsApi.create(payload);
      if (submit && (saved.owner_id !== rmId || !saved.assigned_at || coordinator)) {
        await prospectsApi.assign(saved.id, { rm_id: rmId, comments: form.assignor_comments || null });
      }
      toast.success(submit ? `Prospect submitted to ${userById[rmId]?.name || "the RM"}` : "Prospect saved");
      setModal(false); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };

  const move = async (p, status) => {
    try { await prospectsApi.update(p.id, { status }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const doAssign = async () => {
    try {
      await prospectsApi.assign(assign.prospect.id, { rm_id: Number(assign.rm_id), comments: assign.comments || null });
      toast.success("Prospect assigned");
      setAssign(null); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Assignment failed"); }
  };
  const createClient = (p) => onNavigate?.({ page: "accounts", prospectId: p.id });

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <PageHeader title="Prospects"
        subtitle={`${items.length} prospect${items.length === 1 ? "" : "s"}`}
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
                      {p.notes && <div className="line-clamp-2" title={p.notes}>Looking for: {p.notes}</div>}
                    </div>
                    {p.converted_account_id && (
                      <button onClick={() => onNavigate?.({ page: "accounts", accountId: p.converted_account_id })}
                        className="mt-1 text-[11px] text-emerald-700 hover:underline">Client created. Open</button>
                    )}
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
                      {!p.converted_account_id && PROSPECT_STATUS_OPTIONS.filter((s) => s !== p.status).map((s) => (
                        <button key={s} onClick={() => move(p, s)} className="text-xs px-2 py-0.5 rounded border border-gray-200 text-gray-500 hover:bg-gray-50">{s}</button>
                      ))}
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
          <Field label="Prospect's Name" required><Input value={form.company_name || ""} onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))} /></Field>
          <DuplicateWarning name={form.company_name} excludeId={form.id} checkFn={prospectsApi.checkDuplicate} active={!form.id} />
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Contact Name"><Input value={form.contact_name || ""} onChange={(e) => setForm((p) => ({ ...p, contact_name: e.target.value }))} /></Field>
            <Field label="Contact Email"><Input type="email" placeholder="name@domain.com" value={form.contact_email || ""} onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))} /></Field>
            <Field label="Contact Phone"><Input value={form.contact_phone || ""} onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))} /></Field>
            <Field label="Source">
              <SelectWithOther value={form.source} options={PROSPECT_SOURCE_OPTIONS} maxLength={50} otherPlaceholder="Where did the prospect come from?"
                onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))} />
            </Field>
            {coordinator ? (
              <Field label="Submit to RM">
                <Select value={form.owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, owner_id: e.target.value }))}>
                  <option value="">— choose when submitting —</option>
                  {users.filter(isRelationshipManager).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
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
          </div>
          {form.status === "Lost" && (
            <Field label="Lost Reason"><Textarea value={form.lost_reason || ""} onChange={(e) => setForm((p) => ({ ...p, lost_reason: e.target.value }))} /></Field>
          )}
          <Field label="Services the prospect is looking for"><Textarea placeholder="Give details" value={form.notes || ""} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></Field>
          {coordinator && !form.converted_account_id && (
            <Field label="Assignor's comments (optional)">
              <Textarea rows={3} value={form.assignor_comments || ""} onChange={(e) => setForm((p) => ({ ...p, assignor_comments: e.target.value }))} />
              <div className={`text-[11px] text-right mt-0.5 ${wordCount(form.assignor_comments) > 250 ? "text-red-600" : "text-gray-400"}`}>{wordCount(form.assignor_comments)} / 250 words · sent to the RM on Submit</div>
            </Field>
          )}
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={() => save(false)} className="px-4 py-2 text-sm border border-brand-300 text-brand-700 rounded-lg hover:bg-brand-50">Save</button>
            {!form.converted_account_id && (
              <button onClick={() => save(true)} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Submit</button>
            )}
          </div>
        </Modal>
      )}

      {assign && (
        <Modal title={`${assign.self ? "Assign to me" : "Assign RM"}: ${assign.prospect.company_name}`} onClose={() => setAssign(null)}>
          <div className="text-xs text-gray-500 mb-3">Prospect <span className="font-mono">{assign.prospect.prospect_uid}</span></div>
          {!assign.self && (
            <Field label="Relationship Manager" required>
              <Select value={assign.rm_id || ""} onChange={(e) => setAssign((a) => ({ ...a, rm_id: e.target.value }))}>
                <option value="">— choose —</option>
                {users.filter(isRelationshipManager).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
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

    </div>
  );
}
