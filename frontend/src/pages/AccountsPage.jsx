import React, { useEffect, useState } from "react";
import { accountsApi, casesApi } from "../api/endpoints";
import { Icon, Badge, Modal, Field, Input, Select, Spinner, ErrorBanner } from "../components/ui";
import { fmt } from "../utils/constants";

const PRIORITY_OPTIONS = ["Low", "Medium", "High"];

export default function AccountsPage() {
  const [accounts, setAccounts] = useState([]);
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [accRes, caseRes] = await Promise.all([accountsApi.list({ limit: 200 }), casesApi.list({ limit: 500 })]);
      setAccounts(accRes.items || []);
      setCases(caseRes.items || []);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load accounts");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setForm({ company_name: "", industry: "", country: "", strategic_priority: "Medium", existing_relationship: "No", key_contacts: "", website: "" });
    setModal(true);
  };

  const save = async () => {
    if (!form.company_name?.trim()) return alert("Company name is required");
    try {
      setSaving(true);
      await accountsApi.create(form);
      setModal(false);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to create account");
    } finally { setSaving(false); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const filtered = accounts.filter((a) => search === "" || a.company_name.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Accounts</h1>
          <p className="text-sm text-gray-500">{accounts.length} accounts · {fmt(accounts.reduce((s, a) => s + Number(a.total_invoiced_amount || 0), 0))} total invoiced</p>
        </div>
        <button onClick={openNew}
          className="flex items-center gap-2 px-4 py-2 text-sm text-white rounded-lg font-medium"
          style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={15} /> New Account
        </button>
      </div>

      <div className="relative max-w-md">
        <Icon name="search" size={15} className="absolute left-3 top-2.5 text-gray-400" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search accounts..."
          className="w-full pl-8 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-blue-400" />
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-16 text-gray-400 text-sm">
          No accounts yet. Click <strong>New Account</strong> to add your first client company.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filtered.map((a) => {
          const isOpen = selectedId === a.id;
          const accountCases = cases.filter((c) => c.account_id === a.id);
          return (
            <div key={a.id}
              onClick={() => setSelectedId(isOpen ? null : a.id)}
              className={`bg-white border rounded-xl p-5 shadow-sm cursor-pointer hover:shadow-md transition-all ${isOpen ? "border-blue-400 ring-1 ring-blue-200" : "border-gray-100"}`}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm"
                    style={{ background: "#2B6D9A" }}>
                    {a.company_name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-gray-800">{a.company_name}</h3>
                    <p className="text-xs text-gray-500">{a.industry || "—"} · {a.country || "—"}</p>
                  </div>
                </div>
                <Badge text={a.strategic_priority} />
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-500">Invoiced</p>
                  <p className="text-sm font-bold text-gray-800">{fmt(a.total_invoiced_amount)}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-500">Cases</p>
                  <p className="text-sm font-bold text-gray-800">{a.total_cases}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-500">Existing</p>
                  <p className="text-sm font-bold text-gray-800">{a.existing_relationship}</p>
                </div>
              </div>
              {isOpen && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-xs font-semibold text-gray-600 mb-2">Key Contacts</p>
                  <p className="text-xs text-gray-600 mb-3">{a.key_contacts || "—"}</p>
                  <p className="text-xs font-semibold text-gray-600 mb-2">Cases ({accountCases.length})</p>
                  <div className="space-y-1.5">
                    {accountCases.map((c) => (
                      <div key={c.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                        <div className="flex-1 min-w-0 mr-2">
                          <div className="text-xs font-medium text-gray-700 truncate">{c.case_uid}</div>
                          <Badge text={c.stage} />
                        </div>
                        <span className="text-xs font-bold" style={{ color: "#2B6D9A" }}>{fmt(c.invoice_amount)}</span>
                      </div>
                    ))}
                    {accountCases.length === 0 && <p className="text-xs text-gray-400">No cases yet.</p>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {modal && (
        <Modal title="New Account" onClose={() => setModal(false)}>
          <div className="space-y-3">
            <Field label="Company Name *">
              <Input value={form.company_name} onChange={(e) => setForm({ ...form, company_name: e.target.value })} placeholder="e.g. Al Futtaim Group" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Industry">
                <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} placeholder="e.g. Fintech" />
              </Field>
              <Field label="Country">
                <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} placeholder="e.g. UAE" />
              </Field>
            </div>
            <Field label="Website">
              <Input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="e.g. https://company.com" />
            </Field>
            <Field label="Key Contacts">
              <Input value={form.key_contacts} onChange={(e) => setForm({ ...form, key_contacts: e.target.value })} placeholder="e.g. John Smith - CEO" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Strategic Priority">
                <Select value={form.strategic_priority} onChange={(e) => setForm({ ...form, strategic_priority: e.target.value })}>
                  {PRIORITY_OPTIONS.map((p) => <option key={p}>{p}</option>)}
                </Select>
              </Field>
              <Field label="Existing Relationship">
                <Select value={form.existing_relationship} onChange={(e) => setForm({ ...form, existing_relationship: e.target.value })}>
                  <option>No</option>
                  <option>Yes</option>
                </Select>
              </Field>
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-5">
            <button onClick={() => setModal(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} disabled={saving}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
              style={{ background: "#2B6D9A" }}>
              {saving ? "Saving..." : "Create Account"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
