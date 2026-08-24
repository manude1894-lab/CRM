import React, { useEffect, useState } from "react";
import { usersApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Spinner, ErrorBanner } from "../components/ui";
import { ROLE_LABEL } from "../utils/constants";

const ROLE_RESPONSIBILITIES = [
  { role: "Admin", desc: "User management, invoicing (raise/mark paid), full case access" },
  { role: "Relationship Manager (RM)", desc: "Owns client relationship — intake through docs collection, sees own cases" },
  { role: "Ops", desc: "Owns regulator application, license tracking, compliance/tax filings" },
  { role: "Screening", desc: "Reviews and approves/rejects CDD/KYC submissions" },
];

export default function AdminPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    try {
      setLoading(true); setError(null);
      setUsers(await usersApi.list());
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load users");
    } finally { setLoading(false); }
  };
  useEffect(() => { if (isAdmin) load(); else setLoading(false); }, [isAdmin]);

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500">
        <div className="text-center">
          <Icon name="warn" size={32} className="mx-auto mb-2 text-amber-400" />
          <p>Access restricted to Admins</p>
        </div>
      </div>
    );
  }

  const save = async () => {
    try {
      if (modal === "new") {
        await usersApi.create(form);
      } else {
        const { id, created_at, updated_at, ...patch } = form;
        if (!patch.password) delete patch.password;
        await usersApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this user?")) return;
    try { await usersApi.delete(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Admin Panel</h1>
          <p className="text-sm text-gray-500">User management · System settings</p>
        </div>
        <button onClick={() => { setForm({ name: "", email: "", password: "", role: "rm", is_active: true }); setModal("new"); }}
          className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#2B6D9A" }}>
          <Icon name="plus" size={14} /> Add User
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">User</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Email</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Role</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Status</th>
              <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center" style={{ background: "#2B6D9A" }}>
                      {u.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                    </div>
                    <span className="text-sm font-medium text-gray-800">{u.name}</span>
                  </div>
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">{u.email}</td>
                <td className="py-3 px-4"><Badge text={u.role} /></td>
                <td className="py-3 px-4">
                  <span className={`text-xs font-medium ${u.is_active ? "text-green-600" : "text-gray-400"}`}>
                    {u.is_active ? "● Active" : "○ Inactive"}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <button onClick={() => { setForm({ ...u, password: "" }); setModal("edit"); }}
                    className="p-1.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600 mr-1">
                    <Icon name="edit" size={14} />
                  </button>
                  <button onClick={() => remove(u.id)}
                    className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                    <Icon name="del" size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">System Information</h3>
          <div className="space-y-2 text-xs text-gray-600">
            <div className="flex justify-between py-2 border-b border-gray-50"><span>Version</span><span className="font-medium">TRIAM CRM v1.0.0</span></div>
            <div className="flex justify-between py-2 border-b border-gray-50"><span>Backend</span><span className="font-medium">FastAPI + PostgreSQL</span></div>
            <div className="flex justify-between py-2 border-b border-gray-50"><span>Auth</span><span className="font-medium">JWT with refresh tokens</span></div>
            <div className="flex justify-between py-2 border-b border-gray-50"><span>Active Users</span><span className="font-medium">{users.filter((u) => u.is_active).length}</span></div>
            <div className="flex justify-between py-2"><span>Roles</span><span className="font-medium">Admin, RM, Ops, Screening</span></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Roles & Responsibilities</h3>
          <div className="space-y-3">
            {ROLE_RESPONSIBILITIES.map((r) => (
              <div key={r.role} className="text-xs">
                <span className="font-semibold text-gray-800">{r.role}</span>
                <p className="text-gray-500 mt-0.5">{r.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {modal && (
        <Modal title={modal === "new" ? "Add User" : `Edit ${form.name}`} onClose={() => setModal(null)}>
          <Field label="Full Name" required><Input value={form.name || ""} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="Email" required><Input type="email" value={form.email || ""} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} /></Field>
          <Field label={modal === "new" ? "Password (required, min 6)" : "Password (leave blank to keep current)"}>
            <Input type="password" value={form.password || ""} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} />
          </Field>
          <Field label="Role">
            <Select value={form.role || "rm"} onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))}>
              <option value="admin">Admin</option>
              <option value="rm">Relationship Manager</option>
              <option value="ops">Ops</option>
              <option value="screening">Screening</option>
            </Select>
          </Field>
          <Field label="Status">
            <Select value={form.is_active ? "true" : "false"} onChange={(e) => setForm((p) => ({ ...p, is_active: e.target.value === "true" }))}>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </Select>
          </Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save User</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
