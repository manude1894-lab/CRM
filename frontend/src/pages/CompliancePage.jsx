import React, { useEffect, useState } from "react";
import { complianceApi } from "../api/endpoints";
import { Icon, Badge, Spinner, ErrorBanner } from "../components/ui";
import { AR_FILING_STATUS_OPTIONS } from "../utils/constants";

const ITEM_LABEL = {
  renewal: "Annual Licence Fee",
  esr_filing: "Economic Substance (ESR)",
  ar_filing: "Annual Return",
  bo_filing: "BO / ROM-RBO Filing",
};
const WINDOWS = [30, 60, 90];

export default function CompliancePage() {
  const [days, setDays] = useState(60);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      setRows(await complianceApi.listUpcoming(days));
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load compliance calendar");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [days]);

  const markDone = async (row) => {
    const msg = row.item === "bo_filing"
      ? `Mark the BO / ROM-RBO filing for ${row.company_name} as filed? This clears the deadline.`
      : `Mark ${ITEM_LABEL[row.item]} for ${row.company_name} as done? This rolls the due date forward.`;
    if (!confirm(msg)) return;
    try {
      await complianceApi.markDone(row.case_id, row.item);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to mark done");
    }
  };

  const setArStatus = async (row, status) => {
    try {
      await complianceApi.setArStatus(row.case_id, status);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to update AR status");
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Compliance Calendar</h1>
          <p className="text-sm text-gray-500">{rows.length} renewals / filings due in the next {days} days</p>
        </div>
        <div className="flex border border-gray-200 rounded-lg overflow-hidden">
          {WINDOWS.map((w) => (
            <button key={w} onClick={() => setDays(w)}
              className={`px-3 py-1.5 text-xs ${days === w ? "bg-gray-100 text-gray-800" : "text-gray-500 hover:bg-gray-50"}`}>
              {w}d
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Case</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Company</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Item</th>
              <th className="text-left py-3 px-4 text-xs font-semibold text-gray-500">Due Date</th>
              <th className="text-right py-3 px-4 text-xs font-semibold text-gray-500">Days Left</th>
              <th className="py-3 px-4 text-xs font-semibold text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={6} className="text-center py-8 text-sm text-gray-400">No upcoming renewals or filings in this window.</td></tr>
            )}
            {rows.map((r, i) => (
              <tr key={`${r.case_id}-${r.item}-${i}`} className="border-b border-gray-50 hover:bg-gray-50">
                <td className="py-3 px-4 text-xs font-medium text-gray-800">{r.case_uid}</td>
                <td className="py-3 px-4 text-xs text-gray-600">{r.company_name}</td>
                <td className="py-3 px-4 text-xs text-gray-600">
                  {r.label || ITEM_LABEL[r.item] || r.item}
                  {r.item === "bo_filing" && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">30-day</span>}
                  {r.item === "ar_filing" && r.ar_filing_status && (
                    <div className="mt-1 flex items-center gap-1.5">
                      <Badge text={r.ar_filing_status} />
                      <select value={r.ar_filing_status} onChange={(e) => setArStatus(r, e.target.value)}
                        className="text-[11px] border border-gray-200 rounded px-1 py-0.5 focus:outline-none">
                        {AR_FILING_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                  )}
                </td>
                <td className="py-3 px-4 text-xs text-gray-600">{r.due_date}</td>
                <td className={`py-3 px-4 text-xs text-right font-medium ${r.days_remaining <= (r.item === "bo_filing" ? 14 : 7) ? "text-red-600" : r.days_remaining <= 30 ? "text-amber-600" : "text-gray-600"}`}>
                  {r.days_remaining}
                </td>
                <td className="py-3 px-4">
                  <button onClick={() => markDone(r)}
                    className="p-1.5 rounded hover:bg-green-50 text-gray-400 hover:text-green-600" title="Mark done">
                    <Icon name="check" size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
