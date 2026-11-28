import React, { useEffect, useMemo, useState } from "react";
import { prospectsApi, usersApi, countriesApi } from "../api/endpoints";
import MobileNumberInput from "../components/MobileNumberInput";
import { dialCodeOptions } from "../utils/dialCodes";
import { mobileProblem, splitPhone, joinPhone, UAE_CODE } from "../utils/mobile";
import { Icon, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner, PageHeader, SelectWithOther, FilterBar, SearchInput } from "../components/ui";
import { PAGE_SIZES, usePageSize } from "../components/listing";
import DuplicateWarning from "../components/DuplicateWarning";
import { PROSPECT_STATUS_OPTIONS, PROSPECT_SOURCE_OPTIONS, COUNTRY_CALLING_CODES, isRelationshipManager, personLabel, fmtDate } from "../utils/constants";
import { toast } from "../store/toast";
import { reasonDialog } from "../store/confirm";
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
 * client from the prospect, whose Prospect ID is the client's temporary ID until the Final approval.
 */
// Status buttons on a prospect card, in the colour of the status they move to.
const MOVE_STYLE = {
  New: "border-gray-200 text-gray-600 hover:bg-gray-50",
  Won: "border-emerald-200 text-emerald-700 hover:bg-emerald-50",
  Dropped: "border-rose-200 text-rose-600 hover:bg-rose-50",
};

const LANE_COLOUR = { New: "bg-brand-500", Won: "bg-emerald-500", Dropped: "bg-slate-400" };
const initials = (name) => (name || "?").split(/\s+/).filter((w) => /[A-Za-z0-9]/.test(w[0] || "")).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?";

export default function ProspectsPage({ onNavigate } = {}) {
  const [items, setItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [perColumn, setPerColumn] = usePageSize("prospects", 15);
  const [more, setMore] = useState({}); // extra sets of cards shown per column
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [assign, setAssign] = useState(null); // { prospect, rm_id, comments }
  const me = useAuthStore((s) => s.user);
  const coordinator = useAuthStore((s) => s.isProspectCoordinator());
  const canOverrideDuplicate = useAuthStore((s) => s.can("client.approve"));
  const readOnly = useAuthStore((s) => s.isReadOnly());

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

  // Contact phone as country code + number, like the client forms (Triam UAT 13-11-2026 row 83); saved as one value.
  const [countries, setCountries] = useState([]);
  useEffect(() => { countriesApi.list().then(setCountries).catch(() => {}); }, []);
  const dialOptions = useMemo(() => dialCodeOptions(countries, COUNTRY_CALLING_CODES), [countries]);
  const openNew = () => { setForm({ ...empty, _phone_code: UAE_CODE, _phone_number: "" }); setModal(true); };
  const openEdit = (p) => {
    const { code, number } = splitPhone(p.contact_phone, dialOptions.map((o) => o.code));
    setForm({ ...p, owner_id: p.owner_id ?? "", proposal_sent_date: p.proposal_sent_date || "", assignor_comments: p.assignor_comments || "",
      _phone_code: code || (p.contact_phone ? "" : UAE_CODE), _phone_number: number });
    setModal(true);
  };

  // Cancel / Save / Submit (Triam input 19-10-2026): Save keeps the prospect without sending it;
  // Submit also sends it to the named RM (BRD §4A assignment: notified, with the assignor's comments).
  const save = async (submit = false) => {
    if (!form.company_name?.trim()) return toast.error("Enter the prospect's name");
    if (!form.notes?.trim()) return toast.error("Enter the services the prospect is looking for");
    if (form.contact_email && !EMAIL_RE.test(form.contact_email.trim())) return toast.error("Enter the contact email as name@domain.com");
    const phoneError = mobileProblem(form._phone_code, form._phone_number, "Contact Phone");
    if (phoneError) return toast.error(phoneError);
    const rmId = coordinator ? (form.owner_id ? Number(form.owner_id) : null) : me?.id;
    if (submit && !rmId) return toast.error("Choose the RM to submit the prospect to");
    if (submit && wordCount(form.assignor_comments) > 250) return toast.error("Assignor's comments can be at most 250 words");
    const { id, prospect_uid, converted_account_id, assigned_by_id, assigned_by_name, assigned_at, assignor_comments,
      owner_name, created_at, updated_at, owner_id, proposal_sent_date, _phone_code, _phone_number, ...fields } = form;
    const payload = {
      ...fields,
      contact_phone: joinPhone(_phone_code, _phone_number) || null,
      contact_email: form.contact_email?.trim() || null,
      lost_reason: form.lost_reason || null,
    };
    const send = (body) => (form.id ? prospectsApi.update(form.id, body) : prospectsApi.create(body));
    try {
      let saved;
      try {
        saved = await send(payload);
      } catch (e) {
        // BRD §3: an exact duplicate is blocked; Compliance may go ahead with a recorded reason.
        if (e.response?.status !== 409 || !canOverrideDuplicate) throw e;
        const reason = await reasonDialog({ title: "Duplicate prospect", confirmLabel: "Create anyway", message: e.response.data.detail });
        if (reason === null) return;
        saved = await send({ ...payload, allow_duplicate: true, duplicate_reason: reason });
      }
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

  // Triam 22-11-2026: a search over the board, and each column shows a set number of cards with "Show more".
  const q = search.trim().toLowerCase();
  const matching = q ? items.filter((p) => [p.company_name, p.contact_name, p.prospect_uid, p.contact_email, userById[p.owner_id]?.name]
    .some((v) => (v || "").toLowerCase().includes(q))) : items;

  return (
    <div className="space-y-4">
      <PageHeader title="Prospects"
        subtitle={`${items.length} prospect${items.length === 1 ? "" : "s"}`}
        actions={!readOnly && <>
<button onClick={openNew} className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 bg-brand-600 hover:bg-brand-700">
          <Icon name="plus" size={14} /> Add Prospect
        </button>
        </>} />

      <FilterBar>
        <SearchInput value={search} onChange={setSearch} placeholder="Search by prospect, contact, PROS ID or RM…" />
        <label className="ml-auto flex items-center gap-1.5 text-xs text-gray-600">
          <span>Cards per column</span>
          <select value={perColumn} onChange={(e) => { setPerColumn(Number(e.target.value)); setMore({}); }} aria-label="Cards per column"
            className="border border-gray-200 rounded-md bg-white px-1.5 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-300">
            {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </FilterBar>

      {/* Each column is at least 220px wide; on a narrow screen the board scrolls sideways instead of overlapping. */}
      <div className="grid grid-cols-1 md:grid-cols-[repeat(3,minmax(260px,1fr))] gap-4 overflow-x-auto pb-2">
        {PROSPECT_STATUS_OPTIONS.map((col) => {
          const colAll = matching.filter((p) => p.status === col);
          const limit = perColumn * (1 + (more[col] || 0));
          const colItems = colAll.slice(0, limit);
          return (
            <div key={col} className="min-w-0 rounded-xl bg-slate-100/60 border border-slate-200/60 p-2">
              {/* Triam 22-11-2026 design refresh: a lane per status, its colour on top. */}
              <div className={`h-1 rounded-full mb-2 ${LANE_COLOUR[col] || "bg-slate-300"}`} />
              <div className="flex items-center justify-between mb-2 px-1">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-600">{col}</span>
                <span className="text-[11px] font-semibold text-slate-500 bg-white border border-slate-200 rounded-full px-2 py-0.5">{colAll.length}</span>
              </div>
              <div className="space-y-2 min-h-16">
                {colItems.length === 0 && <div className="text-xs text-slate-600 text-center py-8">{q ? "No matches" : "No prospects"}</div>}
                {colItems.map((p) => (
                  <div key={p.id} className="bg-white border border-gray-200/70 rounded-xl p-3 shadow-[0_1px_2px_rgba(16,24,40,0.05)] hover:shadow-md transition-shadow">
                    <div className="flex items-start gap-2.5">
                      <span className="w-8 h-8 rounded-lg bg-brand-50 text-brand-700 text-[11px] font-bold flex items-center justify-center flex-shrink-0">{initials(p.company_name)}</span>
                      <div className="min-w-0 flex-1">
                        <button onClick={() => openEdit(p)} className="block text-[13px] font-semibold text-gray-900 text-left leading-snug hover:text-brand-600">{p.company_name}</button>
                        <span className="inline-block mt-0.5 font-mono text-[10px] text-gray-600 bg-gray-100 rounded px-1.5 py-px">{p.prospect_uid}</span>
                      </div>
                    </div>
                    {p.contact_name && <div className="text-xs text-gray-600 mt-2">{p.contact_name}</div>}
                    <div className="text-[11px] text-gray-500 mt-1 space-y-0.5">
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
                    {!readOnly && <div className="flex items-center gap-1 mt-2.5 pt-2.5 border-t border-gray-100 flex-wrap empty:hidden" onClick={(e) => e.stopPropagation()}>
                      {!p.converted_account_id && coordinator && (
                        <button onClick={() => setAssign({ prospect: p, rm_id: p.owner_id || "", comments: p.assignor_comments || "" })}
                          className="text-xs px-2.5 py-1 rounded-md border border-sky-200 bg-sky-50 text-sky-800 font-medium hover:bg-sky-100">{p.owner_id ? "Reassign" : "Assign"}</button>
                      )}
                      {!p.converted_account_id && !coordinator && !p.owner_id && (
                        <button onClick={() => setAssign({ prospect: p, rm_id: me?.id, comments: "", self: true })}
                          className="text-xs px-2.5 py-1 rounded-md border border-sky-200 bg-sky-50 text-sky-800 font-medium hover:bg-sky-100">Assign to me</button>
                      )}
                      {!p.converted_account_id && p.owner_id && p.status !== "Dropped" && (coordinator || p.owner_id === me?.id || me?.role === "admin") && (
                        <button onClick={() => createClient(p)} className="text-xs px-2.5 py-1 rounded-md bg-emerald-600 text-white font-medium shadow-sm hover:bg-emerald-700">Create client</button>
                      )}
                    </div>}
                    {/* Status moves on their own line, each in its status colour (Triam UAT 11-11-2026). */}
                    {!readOnly && !p.converted_account_id && (
                      <div className="flex items-center gap-1 mt-1.5 flex-wrap" onClick={(e) => e.stopPropagation()}>
                        {PROSPECT_STATUS_OPTIONS.filter((s) => s !== p.status).map((s) => (
                          <button key={s} onClick={() => move(p, s)}
                            className={`text-[11px] px-2 py-0.5 rounded-full border ${MOVE_STYLE[s] || "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>{s}</button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {colAll.length > colItems.length && (
                  <button type="button" onClick={() => setMore((m) => ({ ...m, [col]: (m[col] || 0) + 1 }))}
                    className="w-full py-2 text-xs font-medium text-brand-700 bg-white/70 border border-dashed border-slate-300 rounded-lg hover:bg-white">
                    Show {Math.min(perColumn, colAll.length - colItems.length)} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {modal && (
        <Modal title={readOnly ? "Prospect" : form.id ? "Edit Prospect" : "New Prospect"} onClose={() => setModal(false)}>
          <fieldset disabled={readOnly} className="min-w-0">
          <Field label="Prospect's Name" required><Input value={form.company_name || ""} onChange={(e) => setForm((p) => ({ ...p, company_name: e.target.value }))} /></Field>
          <DuplicateWarning name={form.company_name} excludeId={form.id} checkFn={prospectsApi.checkDuplicate} active={!form.id} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
            <Field label="Contact Name"><Input value={form.contact_name || ""} onChange={(e) => setForm((p) => ({ ...p, contact_name: e.target.value }))} /></Field>
            <Field label="Contact Email"><Input type="email" placeholder="name@domain.com" value={form.contact_email || ""} onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))} /></Field>
            <div className="sm:col-span-2">
              <Field label="Contact Phone">
                <MobileNumberInput code={form._phone_code} number={form._phone_number} options={dialOptions}
                  onCode={(v) => setForm((p) => ({ ...p, _phone_code: v }))} onNumber={(v) => setForm((p) => ({ ...p, _phone_number: v }))} />
              </Field>
            </div>
            <Field label="Source">
              <SelectWithOther value={form.source} options={PROSPECT_SOURCE_OPTIONS} maxLength={50} otherPlaceholder="Where did the prospect come from?"
                onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))} />
            </Field>
            {coordinator ? (
              <Field label="Submit to RM" required>
                <Select value={form.owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, owner_id: e.target.value }))}>
                  <option value="">— choose when submitting —</option>
                  {users.filter(isRelationshipManager).map((u, _, rms) => <option key={u.id} value={u.id}>{personLabel(u, rms)}</option>)}
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
          </div>
          {form.status === "Dropped" && (
            <Field label="Reason for dropping"><Textarea value={form.lost_reason || ""} onChange={(e) => setForm((p) => ({ ...p, lost_reason: e.target.value }))} /></Field>
          )}
          <Field label="Services the prospect is looking for" required><Textarea placeholder="Give details" value={form.notes || ""} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></Field>
          {coordinator && !form.converted_account_id && (
            <Field label="Assignor's comments (optional)">
              <Textarea rows={3} value={form.assignor_comments || ""} onChange={(e) => setForm((p) => ({ ...p, assignor_comments: e.target.value }))} />
              <div className={`text-[11px] text-right mt-0.5 ${wordCount(form.assignor_comments) > 250 ? "text-red-600" : "text-gray-500"}`}>{wordCount(form.assignor_comments)} / 250 words · sent to the RM on Submit</div>
            </Field>
          )}
          {/* Stamped by the system when the prospect is submitted to the RM (Triam UAT 26-10-2026). */}
          <p className="text-xs text-gray-500 mt-1">Proposal Sent Date: <span className="font-medium text-gray-700">
            {form.proposal_sent_date ? fmtDate(form.proposal_sent_date) : "—"}</span></p>
          </fieldset>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">{readOnly ? "Close" : "Cancel"}</button>
            {!readOnly && <button onClick={() => save(false)} className="px-4 py-2 text-sm border border-brand-300 text-brand-700 rounded-lg hover:bg-brand-50">Save</button>}
            {!readOnly && !form.converted_account_id && (
              <button onClick={() => save(true)} className="px-4 py-2 text-sm text-white rounded-lg bg-brand-600 hover:bg-brand-700">Submit</button>
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
                {users.filter(isRelationshipManager).map((u, _, rms) => <option key={u.id} value={u.id}>{personLabel(u, rms)}</option>)}
              </Select>
            </Field>
          )}
          <Field label="Assignor's comments (optional)">
            <Textarea rows={4} value={assign.comments} onChange={(e) => setAssign((a) => ({ ...a, comments: e.target.value }))} maxLength={4000} />
            <div className={`text-[11px] text-right mt-0.5 ${wordCount(assign.comments) > 250 ? "text-red-600" : "text-gray-500"}`}>{wordCount(assign.comments)} / 250 words</div>
          </Field>
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setAssign(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={doAssign} disabled={!assign.rm_id || wordCount(assign.comments) > 250}
              className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 bg-brand-600 hover:bg-brand-700">Assign</button>
          </div>
        </Modal>
      )}

    </div>
  );
}
