import React, { useEffect, useMemo, useState } from "react";
import { prospectsApi, usersApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Textarea, Spinner, ErrorBanner } from "../components/ui";
import { PROSPECT_STATUS_OPTIONS, CASE_SOURCE_OPTIONS, JURISDICTION_OPTIONS, SERVICE_TYPE_OPTIONS, fmtFull } from "../utils/constants";

const empty = {
  company_name: "", contact_name: "", contact_email: "", contact_phone: "",
  source: "Referral", owner_id: "", status: "New", proposal_sent_date: "",
  proposal_amount: "", expected_close_date: "", next_follow_up_date: "",
  lost_reason: "", notes: "",
};

export default function ProspectsPage() {
  const [items, setItems] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [convertProspect, setConvertProspect] = useState(null);
  const [convertForm, setConvertForm] = useState({ jurisdiction: "BVI", service_type: "Company Formation", rm_id: "" });

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
        const { id, prospect_uid, converted_case_id, created_at, updated_at, ...patch } = payload;
        await prospectsApi.update(form.id, patch);
      } else {
        await prospectsApi.create(payload);
      }
      setModal(false); load();
    } catch (e) { alert(e.response?.data?.detail || "Save failed"); }
  };

  const move = async (p, status) => {
    try { await prospectsApi.update(p.id, { status }); load(); }
    catch (e) { alert(e.response?.data?.detail || "Update failed"); }
  };

  const remove = async (p) => {
    if (!confirm(`Delete prospect "${p.company_name}"?`)) return;
    try { await prospectsApi.delete(p.id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

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
    } catch (e) { alert(e.response?.data?.detail || "Convert failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Prospects</h1>
          <p className="text-sm text-gray-500">{items.length} tracked leads / proposals — not yet onboarded clients</p>
        </div>
        <button onClick={openNew} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={14} /> Add Prospect
        </button>
      </div>

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
                      <button onClick={() => openEdit(p)} className="text-xs font-semibold text-gray-800 text-left hover:text-blue-600">{p.company_name}</button>
                    </div>
                    <div className="text-[11px] text-gray-400 mt-1">{p.prospect_uid}</div>
                    {p.contact_name && <div className="text-xs text-gray-500 mt-1">{p.contact_name}</div>}
                    <div className="text-[11px] text-gray-400 mt-1 space-y-0.5">
                      {p.owner_id && <div>{userById[p.owner_id]?.name || `User #${p.owner_id}`}</div>}
                      {p.proposal_amount && <div>{fmtFull(p.proposal_amount)}</div>}
                      {p.next_follow_up_date && <div>Follow up {p.next_follow_up_date}</div>}
                    </div>
                    {p.converted_case_id && (
                      <div className="mt-1"><Badge text="Converted" /></div>
                    )}
                    <div className="flex items-center gap-1 mt-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
                      {p.status === "Won" && !p.converted_case_id && (
                        <button onClick={() => openConvert(p)} className="text-xs px-2 py-0.5 rounded border border-gray-200 text-green-600 hover:bg-green-50">Convert to Case</button>
                      )}
                      {!p.converted_case_id && PROSPECT_STATUS_OPTIONS.filter((s) => s !== p.status).map((s) => (
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
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Contact Name"><Input value={form.contact_name || ""} onChange={(e) => setForm((p) => ({ ...p, contact_name: e.target.value }))} /></Field>
            <Field label="Contact Email"><Input value={form.contact_email || ""} onChange={(e) => setForm((p) => ({ ...p, contact_email: e.target.value }))} /></Field>
            <Field label="Contact Phone"><Input value={form.contact_phone || ""} onChange={(e) => setForm((p) => ({ ...p, contact_phone: e.target.value }))} /></Field>
            <Field label="Source">
              <Select value={form.source || "Referral"} onChange={(e) => setForm((p) => ({ ...p, source: e.target.value }))}>
                {CASE_SOURCE_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            <Field label="Owner">
              <Select value={form.owner_id || ""} onChange={(e) => setForm((p) => ({ ...p, owner_id: e.target.value }))}>
                <option value="">— Unassigned —</option>
                {users.filter((u) => u.role === "rm").map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select>
            </Field>
            <Field label="Status">
              <Select value={form.status || "New"} onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}>
                {PROSPECT_STATUS_OPTIONS.map((x) => <option key={x}>{x}</option>)}
              </Select>
            </Field>
            <Field label="Proposal Sent Date"><Input type="date" value={form.proposal_sent_date || ""} onChange={(e) => setForm((p) => ({ ...p, proposal_sent_date: e.target.value }))} /></Field>
            <Field label="Proposal Amount"><Input type="number" min="0" step="0.01" value={form.proposal_amount ?? ""} onChange={(e) => setForm((p) => ({ ...p, proposal_amount: e.target.value }))} /></Field>
            <Field label="Expected Close Date"><Input type="date" value={form.expected_close_date || ""} onChange={(e) => setForm((p) => ({ ...p, expected_close_date: e.target.value }))} /></Field>
            <Field label="Next Follow-up Date"><Input type="date" value={form.next_follow_up_date || ""} onChange={(e) => setForm((p) => ({ ...p, next_follow_up_date: e.target.value }))} /></Field>
          </div>
          {form.status === "Lost" && (
            <Field label="Lost Reason"><Textarea value={form.lost_reason || ""} onChange={(e) => setForm((p) => ({ ...p, lost_reason: e.target.value }))} /></Field>
          )}
          <Field label="Notes"><Textarea value={form.notes || ""} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} /></Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
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
            <button onClick={doConvert} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Convert</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
