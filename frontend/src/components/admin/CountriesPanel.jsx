import React, { useEffect, useMemo, useState } from "react";
import { auditApi, countriesApi } from "../../api/endpoints";
import { Field, Input, Select, Spinner, ErrorBanner, SearchInput } from "../ui";
import AuditTrail from "../AuditTrail";
import { toast } from "../../store/toast";
import { fmtDate } from "../../utils/constants";

const RISKS = ["High", "Medium", "Low"];
const RISK_STYLE = { High: "bg-red-50 text-red-700", Medium: "bg-amber-50 text-amber-800", Low: "bg-emerald-50 text-emerald-700" };
const BLANK = { name: "", code: "", risk_level: "Low" };

// BRD §17 — the country list behind every country drop-down (UAE shown first), with each country's
// ISO code and risk level. Last changed is stamped by the system; History shows every change.
export default function CountriesPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [adding, setAdding] = useState(null);
  const [editing, setEditing] = useState(null); // { id, code, risk_level }
  const [history, setHistory] = useState(null); // { id, entries, loading }

  const load = async () => {
    try { setLoading(true); setError(null); setRows(await countriesApi.list()); }
    catch (e) { setError(e.response?.data?.detail || "Failed to load countries"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => (!q || r.name.toLowerCase().includes(q) || (r.code || "").toLowerCase() === q)
      && (!riskFilter || r.risk_level === riskFilter)).sort((a, b) => a.name.localeCompare(b.name));
  }, [rows, search, riskFilter]);

  const add = async () => {
    const name = adding.name.trim();
    if (!name) return toast.error("Enter the country name");
    if (adding.code && !/^[A-Za-z]{2}$/.test(adding.code)) return toast.error("The country code has two letters, e.g. AE");
    try {
      await countriesApi.create({ name, code: adding.code || null, risk_level: adding.risk_level });
      setAdding(null); load(); toast.success(`${name} added`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not add the country"); }
  };

  const save = async () => {
    if (editing.code && !/^[A-Za-z]{2}$/.test(editing.code)) return toast.error("The country code has two letters, e.g. AE");
    try {
      await countriesApi.update(editing.id, { code: editing.code || null, risk_level: editing.risk_level });
      setEditing(null); load(); toast.success("Country updated");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not update the country"); }
  };

  const showHistory = async (r) => {
    if (history?.id === r.id) return setHistory(null);
    setHistory({ id: r.id, entries: [], loading: true });
    try {
      const { items } = await auditApi.list({ subject_type: "Country", subject_id: r.id, limit: 100 });
      setHistory({ id: r.id, entries: items, loading: false });
    } catch { setHistory({ id: r.id, entries: [], loading: false }); }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="w-64"><SearchInput value={search} onChange={setSearch} placeholder="Search countries or code" /></div>
        <div className="w-40"><Select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
          <option value="">All risk levels</option>
          {RISKS.map((r) => <option key={r} value={r}>{r} risk</option>)}
        </Select></div>
        <span className="text-xs text-gray-400">{rows.length} countries</span>
        {adding === null && (
          <button onClick={() => setAdding({ ...BLANK })}
            className="ml-auto px-3 py-1.5 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Add country</button>
        )}
      </div>
      {adding !== null && (
        <div className="flex flex-wrap items-end gap-2 p-3 mb-3 rounded-lg border border-brand-100 bg-brand-50/40">
          <div className="w-64"><Field label="Country"><Input autoFocus value={adding.name} onChange={(e) => setAdding((a) => ({ ...a, name: e.target.value }))} /></Field></div>
          <div className="w-24"><Field label="Code"><Input value={adding.code} maxLength={2} placeholder="AE" onChange={(e) => setAdding((a) => ({ ...a, code: e.target.value.toUpperCase() }))} /></Field></div>
          <div className="w-36"><Field label="Country risk"><Select value={adding.risk_level} onChange={(e) => setAdding((a) => ({ ...a, risk_level: e.target.value }))}>
            {RISKS.map((r) => <option key={r}>{r}</option>)}
          </Select></Field></div>
          <div className="flex gap-2 mb-4">
            <button onClick={() => setAdding(null)} className="px-3 py-2 text-xs border border-gray-200 rounded-lg bg-white">Cancel</button>
            <button onClick={add} className="px-3 py-2 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Add</button>
          </div>
        </div>
      )}
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <div className="max-h-[60vh] overflow-y-auto border border-gray-100 rounded-lg">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="text-left py-2 px-3 font-medium">Country</th>
                <th className="text-left py-2 px-3 font-medium">Code</th>
                <th className="text-left py-2 px-3 font-medium">Country risk</th>
                <th className="text-left py-2 px-3 font-medium">Last changed</th>
                <th className="py-2 px-3" />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <React.Fragment key={r.id}>
                  <tr className="border-t border-gray-50">
                    <td className="py-1.5 px-3 text-gray-800">{r.name}</td>
                    {editing?.id === r.id ? (
                      <>
                        <td className="py-1 px-3"><Input className="!w-16" value={editing.code} maxLength={2}
                          onChange={(e) => setEditing((x) => ({ ...x, code: e.target.value.toUpperCase() }))} /></td>
                        <td className="py-1 px-3"><Select className="!w-28" value={editing.risk_level} onChange={(e) => setEditing((x) => ({ ...x, risk_level: e.target.value }))}>
                          {RISKS.map((x) => <option key={x}>{x}</option>)}
                        </Select></td>
                        <td className="py-1.5 px-3 text-xs text-gray-500">{fmtDate(r.changed_at) || "—"}</td>
                        <td className="py-1 px-3 text-right whitespace-nowrap">
                          <button onClick={() => setEditing(null)} className="px-2 py-1 text-xs border border-gray-200 rounded-lg mr-1">Cancel</button>
                          <button onClick={save} className="px-2 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Save</button>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-1.5 px-3 font-mono text-xs text-gray-600">{r.code || "—"}</td>
                        <td className="py-1.5 px-3">{r.risk_level
                          ? <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${RISK_STYLE[r.risk_level] || "bg-gray-100 text-gray-600"}`}>{r.risk_level}</span> : "—"}</td>
                        <td className="py-1.5 px-3 text-xs text-gray-500">{fmtDate(r.changed_at) || "—"}</td>
                        <td className="py-1.5 px-3 text-right whitespace-nowrap">
                          <button onClick={() => setEditing({ id: r.id, code: r.code || "", risk_level: r.risk_level || "Low" })}
                            className="px-2 py-1 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 mr-1">Edit</button>
                          <button onClick={() => showHistory(r)}
                            className={`px-2 py-1 text-xs border rounded-lg ${history?.id === r.id ? "border-brand-300 text-brand-700" : "border-gray-200 hover:bg-gray-50"}`}>History</button>
                        </td>
                      </>
                    )}
                  </tr>
                  {history?.id === r.id && (
                    <tr className="bg-gray-50/60"><td colSpan={5} className="px-3 py-2">
                      <AuditTrail entries={history.entries} loading={history.loading} emptyText="No changes recorded yet." />
                    </td></tr>
                  )}
                </React.Fragment>
              ))}
              {shown.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-xs text-gray-400">No countries match.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
