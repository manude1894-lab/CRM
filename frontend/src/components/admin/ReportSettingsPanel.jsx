import React, { useEffect, useState } from "react";
import { reportsApi } from "../../api/endpoints";
import { Button, Input, Spinner } from "../ui";
import { toast } from "../../store/toast";

/**
 * Admin → Reports (Triam 26-11-2026): for each report, by its ID, the Administrator may rename it, hide it, choose
 * the roles that run it (or keep the standard access) and set its default period. Administrators and Inquiry &
 * Reports always see every report. Each change is recorded in the audit log.
 */
const draftOf = (r) => ({ name: r.name || "", hidden: r.hidden, chosen: r.role_ids !== null && r.role_ids !== undefined,
  role_ids: r.role_ids || [], default_days: r.default_days ?? "" });

export default function ReportSettingsPanel({ roles = [] }) {
  const [rows, setRows] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [busy, setBusy] = useState(null);
  const activeRoles = roles.filter((r) => r.is_active !== false);

  const load = () => reportsApi.settings().then((list) => {
    setRows(list);
    setDrafts(Object.fromEntries(list.map((r) => [r.key, draftOf(r)])));
  }).catch(() => setRows([]));
  useEffect(() => { load(); }, []);

  if (rows === null) return <Spinner />;
  const set = (key, patch) => setDrafts((d) => ({ ...d, [key]: { ...d[key], ...patch } }));
  const dirty = (r) => JSON.stringify(draftOf(r)) !== JSON.stringify(drafts[r.key]);
  const save = async (r) => {
    const d = drafts[r.key];
    if (d.chosen && !d.role_ids.length) return toast.error("Choose at least one role, or keep the standard access");
    setBusy(r.key);
    try {
      const saved = await reportsApi.saveSetting(r.key, { name: d.name.trim() || null, hidden: d.hidden,
        role_ids: d.chosen ? d.role_ids : null, default_days: r.takes_days && d.default_days !== "" ? Number(d.default_days) : null });
      setRows((list) => list.map((x) => (x.key === r.key ? saved : x)));
      setDrafts((all) => ({ ...all, [r.key]: draftOf(saved) }));
      toast.success(`${r.code} saved`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save"); } finally { setBusy(null); }
  };

  const groups = [...new Set(rows.map((r) => r.group))];
  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <section key={g} className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-x-auto">
          <h2 className="px-4 pt-3 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">{g}</h2>
          <table className="w-full text-sm">
            <thead><tr className="border-y border-gray-100 bg-gray-50 text-xs text-gray-500">
              {["ID", "Report name", "Shown", "Who can run it", "Default days", ""].map((h) => (
                <th key={h} className="text-left py-2 px-3 font-semibold uppercase tracking-wide whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {rows.filter((r) => r.group === g).map((r) => {
                const d = drafts[r.key];
                return (
                  <tr key={r.key} className="border-b border-gray-50 align-top">
                    <td className="py-2.5 px-3 font-mono text-xs text-gray-600 whitespace-nowrap">{r.code}</td>
                    <td className="py-2 px-3 min-w-[16rem]">
                      <Input aria-label={`Name of ${r.code}`} value={d.name} placeholder={r.standard_title} maxLength={150}
                        onChange={(e) => set(r.key, { name: e.target.value })} />
                    </td>
                    <td className="py-2.5 px-3">
                      <input type="checkbox" aria-label={`Show ${r.code}`} checked={!d.hidden} onChange={(e) => set(r.key, { hidden: !e.target.checked })} />
                    </td>
                    <td className="py-2 px-3 min-w-[18rem]">
                      <select aria-label={`Who can run ${r.code}`} value={d.chosen ? "roles" : "standard"}
                        onChange={(e) => set(r.key, { chosen: e.target.value === "roles" })}
                        className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white">
                        <option value="standard">Standard: {r.standard_access}</option>
                        <option value="roles">Chosen roles</option>
                      </select>
                      {d.chosen && (
                        <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
                          {activeRoles.map((role) => (
                            <label key={role.id} className="flex items-center gap-1.5 text-xs text-gray-700">
                              <input type="checkbox" checked={d.role_ids.includes(role.id)}
                                onChange={(e) => set(r.key, { role_ids: e.target.checked ? [...d.role_ids, role.id] : d.role_ids.filter((x) => x !== role.id) })} />
                              {role.name}
                            </label>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="py-2 px-3 w-28">
                      {r.takes_days ? <Input type="number" min="0" max="3650" aria-label={`Default days of ${r.code}`} value={d.default_days}
                        placeholder={String(r.standard_days)} onChange={(e) => set(r.key, { default_days: e.target.value })} /> : <span className="text-gray-400">—</span>}
                    </td>
                    <td className="py-2 px-3 text-right">
                      <Button size="sm" variant={dirty(r) ? "primary" : "secondary"} disabled={!dirty(r) || busy === r.key} onClick={() => save(r)}>
                        {busy === r.key ? "Saving…" : "Save"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ))}
    </div>
  );
}
