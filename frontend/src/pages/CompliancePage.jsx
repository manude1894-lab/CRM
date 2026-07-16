import React, { useEffect, useState } from "react";
import { complianceApi } from "../api/endpoints";
import { Icon, Spinner, ErrorBanner } from "../components/ui";

const ITEM_LABEL = { renewal: "Renewal", compliance_filing: "Compliance Filing", tax_filing: "Tax Filing" };
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
    if (!confirm(`Mark ${ITEM_LABEL[row.item]} for ${row.company_name} as done? This rolls the due date forward.`)) return;
    try {
      await complianceApi.markDone(row.case_id, row.item);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to mark done");
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
                <td className="py-3 px-4 text-xs text-gray-600">{ITEM_LABEL[r.item]}</td>
                <td className="py-3 px-4 text-xs text-gray-600">{r.due_date}</td>
                <td className={`py-3 px-4 text-xs text-right font-medium ${r.days_remaining <= 7 ? "text-red-600" : r.days_remaining <= 30 ? "text-amber-600" : "text-gray-600"}`}>
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
