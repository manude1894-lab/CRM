import React, { useEffect, useState } from "react";
import { rolesApi } from "../../api/endpoints";
import { Icon, Modal, Field, Input, Select } from "../ui";
import { toast } from "../../store/toast";
import { confirmDialog } from "../../store/confirm";

const BLANK = { name: "", description: "", department_id: "", permissions: [], is_active: true };

// BRD §15/§18 — business roles (CO, MLRO, RO, FO, Sales Manager, Dy MLRO, …) and their permissions.
export default function RolesPanel({ departments, users, onChanged }) {
  const [roles, setRoles] = useState([]);
  const [perms, setPerms] = useState([]);
  const [form, setForm] = useState(null);

  const load = async () => {
    try {
      const [r, p] = await Promise.all([rolesApi.list(), rolesApi.permissions()]);
      setRoles(r); setPerms(p);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to load roles"); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    const payload = { ...form, department_id: form.department_id ? +form.department_id : null, description: form.description || null };
    try {
      if (form.id) {
        const { id, created_at, updated_at, ...patch } = payload;
        await rolesApi.update(id, patch);
      } else {
        await rolesApi.create(payload);
      }
      setForm(null); load(); onChanged?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); }
  };

  const remove = async (role) => {
    if (!(await confirmDialog(`Delete role "${role.name}"?`))) return;
    try { await rolesApi.delete(role.id); load(); onChanged?.(); }
    catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const togglePerm = (key) => setForm((f) => ({
    ...f, permissions: f.permissions.includes(key) ? f.permissions.filter((p) => p !== key) : [...f.permissions, key],
  }));

  const memberCount = (roleId) => users.filter((u) => u.business_role_id === roleId).length;
  const deptName = (id) => departments.find((d) => d.id === id)?.name;

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
      <div className="flex items-center justify-between p-4 border-b border-gray-100">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Business Roles</h3>
          <p className="text-xs text-gray-400">Roles add permissions on top of a user's system access (Admin / RM / Ops / Screening). Admins have every permission.</p>
        </div>
        <button onClick={() => setForm({ ...BLANK })} className="px-3 py-1.5 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#1a3a5c" }}>
          <Icon name="plus" size={14} /> Add Role
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-2.5 px-4 text-xs font-semibold text-gray-500">Role</th>
              <th className="text-left py-2.5 px-4 text-xs font-semibold text-gray-500">Permissions</th>
              <th className="text-left py-2.5 px-4 text-xs font-semibold text-gray-500">Users</th>
              <th className="text-left py-2.5 px-4 text-xs font-semibold text-gray-500">Status</th>
              <th className="py-2.5 px-4" />
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.id} className="border-b border-gray-50 align-top">
                <td className="py-2.5 px-4">
                  <div className="font-medium text-gray-800">{r.name}</div>
                  <div className="text-xs text-gray-400">{[r.description, deptName(r.department_id)].filter(Boolean).join(" · ")}</div>
                </td>
                <td className="py-2.5 px-4">
                  <div className="flex flex-wrap gap-1">
                    {r.permissions.length === 0 && <span className="text-xs text-gray-400">No extra permissions</span>}
                    {r.permissions.map((p) => <span key={p} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-brand-50 text-brand-700">{p}</span>)}
                  </div>
                </td>
                <td className="py-2.5 px-4 text-xs text-gray-600">{memberCount(r.id)}</td>
                <td className="py-2.5 px-4 text-xs">{r.is_active ? <span className="text-green-600">● Active</span> : <span className="text-gray-400">○ Inactive</span>}</td>
                <td className="py-2.5 px-4 whitespace-nowrap text-right">
                  <button onClick={() => setForm({ ...r, department_id: r.department_id || "", description: r.description || "" })}
                    className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600 mr-1"><Icon name="edit" size={14} /></button>
                  <button onClick={() => remove(r)} className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={14} /></button>
                </td>
              </tr>
            ))}
            {roles.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-xs text-gray-400">No roles yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {form && (
        <Modal title={form.id ? `Edit role — ${form.name}` : "Add Role"} onClose={() => setForm(null)}>
          <Field label="Name" required><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. MLRO" /></Field>
          <Field label="Description"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <Field label="Department (optional)">
            <Select value={form.department_id || ""} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
              <option value="">— Any —</option>
              {departments.filter((d) => d.is_active || d.id === form.department_id).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select>
          </Field>
          <Field label="Permissions">
            <div className="space-y-1.5">
              {perms.map((p) => (
                <label key={p.key} className="flex items-start gap-2 text-xs text-gray-700">
                  <input type="checkbox" className="mt-0.5" checked={form.permissions.includes(p.key)} onChange={() => togglePerm(p.key)} />
                  <span><span className="font-mono text-[11px] text-gray-500">{p.key}</span> — {p.description}</span>
                </label>
              ))}
            </div>
          </Field>
          <label className="flex items-center gap-2 text-xs text-gray-700 mt-2">
            <input type="checkbox" checked={!!form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Active
          </label>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setForm(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save Role</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
