import React, { useEffect, useState } from "react";
import { usersApi, departmentsApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Spinner, ErrorBanner } from "../components/ui";
import { ROLE_LABEL } from "../utils/constants";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";

const ROLE_RESPONSIBILITIES = [
  { role: "Admin", desc: "User management, invoicing (raise/mark paid), full case access" },
  { role: "Relationship Manager (RM)", desc: "Owns client relationship — intake through docs collection, sees own cases" },
  { role: "Ops", desc: "Owns regulator application, license tracking, compliance/tax filings" },
  { role: "Screening", desc: "Reviews and approves/rejects CDD/KYC submissions" },
];

export default function AdminPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [deptName, setDeptName] = useState("");
  const [editingDeptId, setEditingDeptId] = useState(null);
  const [editingDeptName, setEditingDeptName] = useState("");

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [usersRes, deptRes] = await Promise.all([usersApi.list(), departmentsApi.list()]);
      setUsers(usersRes);
      setDepartments(deptRes);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load users");
    } finally { setLoading(false); }
  };
  useEffect(() => { if (isAdmin) load(); else setLoading(false); }, [isAdmin]);

  const departmentName = (id) => departments.find((d) => d.id === id)?.name || "—";

  const addDepartment = async () => {
    if (!deptName.trim()) return;
    try { await departmentsApi.create({ name: deptName.trim() }); setDeptName(""); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to add department"); }
  };

  const saveDepartmentRename = async (id) => {
    if (!editingDeptName.trim()) return;
    try { await departmentsApi.update(id, { name: editingDeptName.trim() }); setEditingDeptId(null); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to rename department"); }
  };

  const removeDepartment = async (id) => {
    if (!(await confirmDialog("Delete this department? Users assigned to it will become unassigned."))) return;
    try { await departmentsApi.delete(id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to delete department"); }
  };

  const toggleDepartmentActive = async (d) => {
    try { await departmentsApi.update(d.id, { is_active: !d.is_active }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to update department status"); }
  };

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
      const payload = {
        ...form,
        department_id: form.department_id ? +form.department_id : null,
        supervisor_id: form.supervisor_id ? +form.supervisor_id : null,
        title: form.title || null,
      };
      if (modal === "new") {
        await usersApi.create(payload);
      } else {
        const { id, created_at, updated_at, ...patch } = payload;
        if (!patch.password) delete patch.password;
        await usersApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id) => {
    if (!(await confirmDialog("Delete this user?"))) return;
    try { await usersApi.delete(id); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
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
        <button onClick={() => { setForm({ name: "", email: "", password: "", role: "rm", is_active: true, department_id: "", title: "", supervisor_id: "" }); setModal("new"); }}
          className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#1a3a5c" }}>
          <Icon name="plus" size={14} /> Add User
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">User</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Email</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Department</th>
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
                    <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center" style={{ background: "#1a3a5c" }}>
                      {u.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-800">{u.name}</div>
                      {u.title && <div className="text-xs text-gray-400">{u.title}</div>}
                    </div>
                  </div>
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">{u.email}</td>
                <td className="py-3 px-4 text-sm text-gray-600">{departmentName(u.department_id)}</td>
                <td className="py-3 px-4"><Badge text={u.role} /></td>
                <td className="py-3 px-4">
                  <span className={`text-xs font-medium ${u.is_active ? "text-green-600" : "text-gray-400"}`}>
                    {u.is_active ? "● Active" : "○ Inactive"}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <button onClick={() => { setForm({ ...u, password: "" }); setModal("edit"); }}
                    className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600 mr-1">
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Departments</h3>
          <div className="space-y-1.5 mb-3">
            {departments.length === 0 && <p className="text-xs text-gray-400">No departments yet.</p>}
            {departments.map((d) => (
              <div key={d.id} className={`flex items-center justify-between p-1.5 rounded-lg ${d.is_active ? "bg-gray-50" : "bg-gray-50 opacity-60"}`}>
                {editingDeptId === d.id ? (
                  <input autoFocus value={editingDeptName} onChange={(e) => setEditingDeptName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveDepartmentRename(d.id)}
                    onBlur={() => saveDepartmentRename(d.id)}
                    className="text-xs border border-gray-200 rounded px-1.5 py-1 flex-1 mr-2" />
                ) : (
                  <span className="text-xs text-gray-700 flex items-center gap-1.5">
                    {d.name}
                    {!d.is_active && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-500">Inactive</span>}
                  </span>
                )}
                <div className="flex gap-1">
                  <button onClick={() => toggleDepartmentActive(d)} title={d.is_active ? "Deactivate" : "Activate"}
                    className={`p-1 rounded hover:bg-gray-100 ${d.is_active ? "text-green-500" : "text-gray-400"}`}>
                    <Icon name="check" size={12} />
                  </button>
                  <button onClick={() => { setEditingDeptId(d.id); setEditingDeptName(d.name); }} className="p-1 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600">
                    <Icon name="edit" size={12} />
                  </button>
                  <button onClick={() => removeDepartment(d.id)} className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                    <Icon name="del" size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <input value={deptName} onChange={(e) => setDeptName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addDepartment()}
              placeholder="New department name" className="flex-1 text-xs border border-gray-200 rounded-lg px-2 py-1.5" />
            <button onClick={addDepartment} className="px-2.5 py-1.5 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Add</button>
          </div>
        </div>
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
          <Field label="Department">
            <Select value={form.department_id || ""} onChange={(e) => setForm((p) => ({ ...p, department_id: e.target.value }))}>
              <option value="">— None —</option>
              {departments.filter((d) => d.is_active || d.id === form.department_id).map((d) => (
                <option key={d.id} value={d.id}>{d.name}{!d.is_active ? " (Inactive)" : ""}</option>
              ))}
            </Select>
          </Field>
          <Field label="Title">
            <Input value={form.title || ""} onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))} placeholder="e.g. Senior Associate" />
          </Field>
          <Field label="Reports To">
            <Select value={form.supervisor_id || ""} onChange={(e) => setForm((p) => ({ ...p, supervisor_id: e.target.value }))}>
              <option value="">— None —</option>
              {users.filter((u) => u.id !== form.id).map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
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
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save User</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
