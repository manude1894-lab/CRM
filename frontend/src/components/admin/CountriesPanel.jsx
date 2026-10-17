import React, { useEffect, useMemo, useState } from "react";
import { amlApi } from "../../api/endpoints";
import { Field, Input, Select, Spinner, ErrorBanner, SearchInput } from "../ui";
import { toast } from "../../store/toast";

const LEVELS = [["Low", 1], ["Medium", 3], ["High", 5], ["Prohibited", 5]];
const scoreFor = (level) => LEVELS.find(([l]) => l === level)?.[1] || 1;
const LEVEL_STYLE = {
  Low: "bg-green-50 text-green-700", Medium: "bg-amber-50 text-amber-700",
  High: "bg-red-50 text-red-700", Prohibited: "bg-gray-800 text-white",
};

// BRD §2 / §17 — the country list used by every country drop-down (UAE shown first), with the AML
// country risk used in risk scoring. Countries are added or re-rated here; none are deleted.
export default function CountriesPanel() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(null);

  const load = async () => {
    try { setLoading(true); setError(null); setRows(await amlApi.countryRisk()); }
    catch (e) { setError(e.response?.data?.detail || "Failed to load countries"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => !q || r.name.toLowerCase().includes(q)).sort((a, b) => a.name.localeCompare(b.name));
  }, [rows, search]);

  const rate = async (r, level) => {
    try {
      const updated = await amlApi.updateCountry(r.id, { risk_level: level, score: scoreFor(level) });
      setRows((all) => all.map((x) => (x.id === r.id ? updated : x)));
    } catch (e) { toast.error(e.response?.data?.detail || "Update failed"); }
  };

  const add = async () => {
    const name = adding.name.trim();
    if (!name) return toast.error("Enter the country name");
    try {
      await amlApi.createCountry({ name, risk_level: adding.risk_level, score: scoreFor(adding.risk_level) });
      setAdding(null); load(); toast.success(`${name} added`);
    } catch (e) { toast.error(e.response?.data?.detail || "Could not add the country"); }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <div className="w-64"><SearchInput value={search} onChange={setSearch} placeholder="Search countries" /></div>
        <span className="text-xs text-gray-400">{rows.length} countries</span>
        {!adding && (
          <button onClick={() => setAdding({ name: "", risk_level: "Low" })}
            className="ml-auto px-3 py-1.5 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Add country</button>
        )}
      </div>
      {adding && (
        <div className="flex flex-wrap items-end gap-2 p-3 mb-3 rounded-lg border border-brand-100 bg-brand-50/40">
          <div className="w-64"><Field label="Country"><Input autoFocus value={adding.name} onChange={(e) => setAdding((a) => ({ ...a, name: e.target.value }))} /></Field></div>
          <div className="w-40"><Field label="AML country risk">
            <Select value={adding.risk_level} onChange={(e) => setAdding((a) => ({ ...a, risk_level: e.target.value }))}>
              {LEVELS.map(([l]) => <option key={l}>{l}</option>)}
            </Select>
          </Field></div>
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
              <tr><th className="text-left py-2 px-3 font-medium">Country</th><th className="text-left py-2 px-3 font-medium">AML country risk</th></tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} className="border-t border-gray-50">
                  <td className="py-1.5 px-3 text-gray-800">{r.name}</td>
                  <td className="py-1.5 px-3">
                    <select value={r.risk_level} onChange={(e) => rate(r, e.target.value)}
                      className={`text-xs rounded px-2 py-0.5 border-0 cursor-pointer ${LEVEL_STYLE[r.risk_level] || ""}`}>
                      {LEVELS.map(([l]) => <option key={l}>{l}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
              {shown.length === 0 && <tr><td colSpan={2} className="py-6 text-center text-xs text-gray-400">No countries match.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
