import React, { useEffect, useState } from "react";
import { workflowApi } from "../api/endpoints";
import { Spinner, ErrorBanner } from "../components/ui";
import { useMasters } from "../hooks/useMasters";
import { formatTimestamp } from "../utils/auditFormat";

const TABS = ["Pending", "Approved", "Rejected", "Withdrawn"];

// BRD §12 step 12 / §15 — the checker's inbox. Opening a row takes the checker to the client
// profile, where the Approve / Reject buttons sit next to the information being reviewed.
export default function ApprovalsPage({ onNavigate }) {
  const [tab, setTab] = useState("Pending");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const reasons = useMasters("rejection_reason", []);

  const load = async () => {
    setLoading(true); setError(null);
    try { setRows(await workflowApi.inbox(tab)); }
    catch (e) { setError(e.response?.data?.detail || "Failed to load approvals"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [tab]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Approvals</h1>
        <p className="text-sm text-gray-500">Client profiles submitted by makers for checker review. You can't approve a profile you submitted yourself.</p>
      </div>
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${tab === t ? "border-brand-500 text-brand-700 font-medium" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t}
          </button>
        ))}
      </div>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                <th className="text-left py-2.5 px-4 font-semibold">Client</th>
                <th className="text-left py-2.5 px-4 font-semibold">Submitted by</th>
                <th className="text-left py-2.5 px-4 font-semibold">Submitted</th>
                {tab !== "Pending" && <th className="text-left py-2.5 px-4 font-semibold">Decision</th>}
                <th className="py-2.5 px-4" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-gray-50 align-top">
                  <td className="py-2.5 px-4">
                    <div className="font-medium text-gray-800">{r.company_name}</div>
                    <div className="text-xs text-gray-400"><span className="font-mono">{r.client_id || "—"}</span> · {r.account_type}</div>
                    {r.maker_comment && <div className="text-xs text-gray-500 mt-0.5">“{r.maker_comment}”</div>}
                  </td>
                  <td className="py-2.5 px-4 text-xs text-gray-600">{r.maker_name || "—"}</td>
                  <td className="py-2.5 px-4 text-xs text-gray-600">{formatTimestamp(r.submitted_at)}</td>
                  {tab !== "Pending" && (
                    <td className="py-2.5 px-4 text-xs text-gray-600">
                      {r.checker_name || "—"} · {formatTimestamp(r.decided_at)}
                      {r.reason_code && <div className="text-red-600">{reasons.labelOf(r.reason_code)} — {r.reason_text}</div>}
                    </td>
                  )}
                  <td className="py-2.5 px-4 text-right">
                    <button onClick={() => onNavigate?.({ page: "accounts", accountId: r.account_id, openForm: true })}
                      className="px-3 py-1.5 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>
                      {tab === "Pending" ? "Review" : "Open"}
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={5} className="py-10 text-center text-sm text-gray-400">{tab === "Pending" ? "Nothing waiting for review." : `No ${tab.toLowerCase()} requests.`}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
