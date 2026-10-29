import React, { useEffect, useState } from "react";
import SystemHealthPanel from "../components/admin/SystemHealthPanel";
import { usersApi, departmentsApi, rolesApi } from "../api/endpoints";
import MasterDataPanel from "../components/admin/MasterDataPanel";
import CountriesPanel from "../components/admin/CountriesPanel";
import RolesPanel from "../components/admin/RolesPanel";
import AuditLogPanel from "../components/admin/AuditLogPanel";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Spinner, ErrorBanner, PageHeader } from "../components/ui";
import { USER_TYPE_LABEL } from "../utils/constants";
import { toast } from "../store/toast";
import { confirmDialog } from "../store/confirm";

const TABS = [
  { key: "users", label: "Users & Departments" },
  { key: "masters", label: "Master Data" },
  { key: "countries", label: "Countries" },
  { key: "roles", label: "Roles" },
  { key: "audit", label: "Audit Log" },
  { key: "health", label: "System Health" },
];


export default function AdminPage() {
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const me = useAuthStore((s) => s.user);
  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [roles, setRoles] = useState([]);
  const [tab, setTab] = useState("users");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState({});
  const [deptName, setDeptName] = useState("");
  const [editingDeptId, setEditingDeptId] = useState(null);
  const [editingDeptName, setEditingDeptName] = useState("");
  const BLANK_ADDON = { business_role_id: "", email: "", password: "" };
  const [addon, setAddon] = useState(BLANK_ADDON); // a new add-on login for the person being edited

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [usersRes, deptRes, rolesRes] = await Promise.all([usersApi.list(), departmentsApi.list(), rolesApi.list().catch(() => [])]);
      setUsers(usersRes);
      setDepartments(deptRes);
      setRoles(rolesRes);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load users");
    } finally { setLoading(false); }
  };
  useEffect(() => { if (isAdmin) load(); else setLoading(false); }, [isAdmin]);

  const departmentName = (id) => departments.find((d) => d.id === id)?.name || "—";
  const roleName = (id) => roles.find((r) => r.id === id)?.name;
  const userById = (id) => users.find((u) => u.id === id);
  // A person has one login per role (Triam 29-10-2026): add-on logins are listed under their main login.
  const ordered = [...users].sort((a, b) => ((a.person_id || a.id) - (b.person_id || b.id)) || ((a.person_id ? 1 : 0) - (b.person_id ? 1 : 0)) || (a.id - b.id));
  const addonsOf = (id) => users.filter((u) => u.person_id === id);

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
    // A new user needs a password (Triam UAT); when editing, blank keeps the current one.
    if (modal === "new" && !(form.password || "").trim()) return toast.error("Enter a password for the new user");
    if (form.password && (form.password.length < 10 || !/[A-Za-z]/.test(form.password) || !/\d/.test(form.password)))
      return toast.error("Password must be at least 10 characters, with letters and numbers");
    try {
      const payload = {
        ...form,
        department_id: form.department_id ? +form.department_id : null,
        supervisor_id: form.supervisor_id ? +form.supervisor_id : null,
        business_role_id: form.business_role_id ? +form.business_role_id : null,
        title: form.title || null,
        mobile: form.mobile || null,
      };
      if (modal === "new") {
        await usersApi.create(payload);
      } else {
        const { id, created_at, updated_at, permissions, person_id, linked_logins, ...patch } = payload;
        if (!patch.password) delete patch.password;
        await usersApi.update(form.id, patch);
      }
      setModal(null); load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  // An add-on login: another role for the same person, with its own email and password.
  const addAddonLogin = async () => {
    if (!addon.business_role_id) return toast.error("Choose the role for the add-on login");
    if (!addon.email.trim()) return toast.error("Enter the email for the add-on login");
    if (addon.password.length < 10 || !/[A-Za-z]/.test(addon.password) || !/\d/.test(addon.password))
      return toast.error("Password must be at least 10 characters, with letters and numbers");
    try {
      await usersApi.create({
        name: form.name, email: addon.email.trim(), password: addon.password, role: "rm", is_active: true,
        business_role_id: +addon.business_role_id, person_id: form.id,
        department_id: form.department_id ? +form.department_id : null, supervisor_id: form.supervisor_id ? +form.supervisor_id : null,
        title: form.title || null, mobile: form.mobile || null,
      });
      toast.success(`Add-on login ${addon.email.trim()} created`);
      setAddon(BLANK_ADDON); load();
    } catch (e) { toast.error(e.response?.data?.detail || "Could not add the login"); }
  };

  // Only the support account may delete a login (e.g. a test account); everyone else deactivates.
  const deleteUser = async (u) => {
    if (!(await confirmDialog({ title: "Delete user", confirmLabel: "Delete", danger: true,
      message: `${u.name} (${u.email}) will be removed permanently. Their past actions stay in the history without their name.` }))) return;
    try { await usersApi.remove(u.id); toast.success("User deleted"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  // Users are never deleted: deactivating ends their access and keeps their history.
  const toggleActive = async (u) => {
    if (u.is_active && !(await confirmDialog({ title: "Deactivate user", confirmLabel: "Deactivate", danger: true,
      message: `${u.name} will no longer be able to sign in. Their history is kept, and they can be reactivated later.` }))) return;
    try { await usersApi.update(u.id, { is_active: !u.is_active }); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <PageHeader title="Administration"
        actions={<>
{tab === "users" && <button onClick={() => { setForm({ name: "", email: "", password: "", role: "rm", is_active: true, department_id: "", title: "", mobile: "", supervisor_id: "", business_role_id: "" }); setAddon(BLANK_ADDON); setModal("new"); }}
          className="px-3 py-2 text-sm text-white rounded-lg font-medium flex items-center gap-1.5 hover:opacity-90" style={{ background: "#1a3a5c" }}>
          <Icon name="plus" size={14} /> Add User
        </button>}
        </>} />

      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${tab === t.key ? "border-brand-500 text-brand-700 font-medium" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "masters" && <MasterDataPanel />}
      {tab === "countries" && <CountriesPanel />}
      {tab === "roles" && <RolesPanel departments={departments} users={users} onChanged={load} />}
      {tab === "audit" && <AuditLogPanel users={users} />}
      {tab === "health" && <SystemHealthPanel />}

      {tab === "users" && (<>
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
            {ordered.map((u) => (
              <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 px-4">
                  <div className={`flex items-center gap-3 ${u.person_id ? "pl-6" : ""}`}>
                    <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center" style={{ background: "#1a3a5c" }}>
                      {u.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-gray-800">{u.name}</div>
                      {u.person_id
                        ? <div className="text-[11px] text-gray-400">Add-on login of {userById(u.person_id)?.email || "their main login"}</div>
                        : u.title && <div className="text-xs text-gray-400">{u.title}</div>}
                    </div>
                  </div>
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">{u.email}</td>
                <td className="py-3 px-4 text-sm text-gray-600">{departmentName(u.department_id)}</td>
                <td className="py-3 px-4">
                  <div className="flex flex-wrap gap-1">
                    {roleName(u.business_role_id) && <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-brand-50 text-brand-700">{roleName(u.business_role_id)}</span>}
                    {u.role === "admin" && <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-red-50 text-red-700">Administrator</span>}
                  </div>
                  {u.role !== "admin" && !u.business_role_id && (
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{USER_TYPE_LABEL[u.role] || u.role}</span>
                  )}
                </td>
                <td className="py-3 px-4">
                  <span className={`text-xs font-medium ${u.is_active ? "text-green-600" : "text-gray-400"}`}>
                    {u.is_active ? "● Active" : "○ Inactive"}
                    {u.locked_until && new Date(u.locked_until) > new Date() && (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded bg-red-50 text-red-700" title="Too many wrong passwords. Set a new password to unlock.">Locked</span>
                    )}
                  </span>
                </td>
                <td className="py-3 px-4">
                  <button onClick={() => { setForm({ ...u, password: "" }); setAddon(BLANK_ADDON); setModal("edit"); }}
                    className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600 mr-1">
                    <Icon name="edit" size={14} />
                  </button>
                  {u.id !== me?.id && <button onClick={() => toggleActive(u)}
                    className={`px-2 py-1 rounded text-[11px] border ${u.is_active ? "border-gray-200 text-gray-500 hover:text-red-600 hover:border-red-200" : "border-green-200 text-green-700 hover:bg-green-50"}`}>
                    {u.is_active ? "Deactivate" : "Activate"}
                  </button>}
                  {me?.is_super_admin && u.id !== me?.id && (
                    <button onClick={() => deleteUser(u)} title="Delete user"
                      className="ml-1 px-2 py-1 rounded text-[11px] border border-red-200 text-red-600 hover:bg-red-50">Delete</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
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
      </div>
      </>)}

      {modal && (
        <Modal title={modal === "new" ? "Add User" : `Edit ${form.name}`} onClose={() => setModal(null)}>
          <Field label="Full Name" required><Input value={form.name || ""} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} /></Field>
          <Field label="Email" required><Input type="email" value={form.email || ""} autoCapitalize="none" onChange={(e) => setForm((p) => ({ ...p, email: e.target.value.replace(/\s/g, "").toLowerCase() }))} /></Field>
          <Field label={modal === "new" ? "Password (at least 10 characters, letters and numbers)" : "Password (leave blank to keep current)"} required={modal === "new"}>
            <Input type="password" value={form.password || ""} onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))} />
          </Field>
          <Field label="User type">
            <Select value={form.role || "rm"} onChange={(e) => setForm((p) => ({ ...p, role: e.target.value }))}>
              {Object.entries(USER_TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </Field>
          {form.person_id && (
            <p className="mb-3 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs text-gray-600">
              Add-on login of <span className="font-medium">{userById(form.person_id)?.name}</span> ({userById(form.person_id)?.email}). It has its own email, password and role.
            </p>
          )}
          <Field label={form.person_id ? "Role" : "Main role (permissions)"}>
            <Select value={form.business_role_id || ""} onChange={(e) => setForm((p) => ({ ...p, business_role_id: e.target.value }))}>
              <option value="">— None —</option>
              {roles.filter((r) => r.is_active || r.id === form.business_role_id).map((r) => <option key={r.id} value={r.id}>{r.name}{r.description ? ` (${r.description})` : ""}</option>)}
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
          {/* BRD §17 — used for SMS notifications once an SMS provider is configured. */}
          <Field label="Mobile (for SMS alerts)">
            <Input value={form.mobile || ""} onChange={(e) => setForm((p) => ({ ...p, mobile: e.target.value }))} placeholder="e.g. +971501234567" />
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
          {/* Triam 29-10-2026: another role for the same person is an add-on login with its own email and
              password; signed in with one login, the person sees the others at the top and can switch. */}
          {modal === "edit" && !form.person_id ? (
            <div className="mt-2 rounded-lg border border-gray-200 p-3">
              <div className="text-xs font-semibold text-gray-700 mb-1">Add-on logins</div>
              <p className="text-[11px] text-gray-500 mb-2">Another role for {form.name || "this person"}, with its own email and password.</p>
              {addonsOf(form.id).length === 0 && <p className="text-xs text-gray-400 mb-2">None yet.</p>}
              {addonsOf(form.id).map((a) => (
                <div key={a.id} className="flex items-center justify-between text-xs py-1 border-b border-gray-50">
                  <span className="text-gray-700">{a.email}</span>
                  <span className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 text-[11px]">{roleName(a.business_role_id) || "—"}</span>
                    <span className={a.is_active ? "text-green-600" : "text-gray-400"}>{a.is_active ? "Active" : "Inactive"}</span>
                  </span>
                </div>
              ))}
              <div className="grid grid-cols-3 gap-2 mt-2">
                <Select value={addon.business_role_id} onChange={(e) => setAddon((p) => ({ ...p, business_role_id: e.target.value }))}>
                  <option value="">— role —</option>
                  {roles.filter((r) => r.is_active && r.id !== +form.business_role_id).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </Select>
                <Input type="email" placeholder="email@asktriam.com" value={addon.email} autoCapitalize="none"
                  onChange={(e) => setAddon((p) => ({ ...p, email: e.target.value.replace(/\s/g, "").toLowerCase() }))} />
                <Input type="password" placeholder="Password" value={addon.password} onChange={(e) => setAddon((p) => ({ ...p, password: e.target.value }))} />
              </div>
              <div className="flex justify-end mt-2">
                <button onClick={addAddonLogin} className="px-3 py-1.5 text-xs border border-brand-300 text-brand-700 rounded-lg hover:bg-brand-50">Add login</button>
              </div>
            </div>
          ) : modal === "new" && (
            <p className="mt-2 text-[11px] text-gray-500">To give this person another role, save the user, then open them and add an add-on login (its own email and password).</p>
          )}
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
