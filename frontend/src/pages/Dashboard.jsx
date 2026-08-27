import React, { useEffect, useState } from "react";
import {
  Tooltip, ResponsiveContainer,
  Funnel, FunnelChart, LabelList,
} from "recharts";
import { dashboardApi } from "../api/endpoints";
import { MetricCard, CustomTooltip, Badge, Spinner, ErrorBanner } from "../components/ui";
import { PIE_COLORS, fmt } from "../utils/constants";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [collapsed, setCollapsed] = useState({});

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      setData(await dashboardApi.get());
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  const kpis = data.kpis;

  const funnelData = (data.stage_breakdown || [])
    .filter((s) => s.count > 0 && s.stage !== "Active")
    .map((s, i) => ({ name: s.stage, value: s.count, fill: PIE_COLORS[i % PIE_COLORS.length] }));

  const toggle = (userId) => setCollapsed((p) => ({ ...p, [userId]: !p[userId] }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Onboarding Dashboard</h1>
        <p className="text-sm text-gray-500">Entity servicing & compliance · real-time pipeline overview</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard label="Open Cases" value={kpis.open_cases} icon="cases" />
        <MetricCard label="Docs Pending" value={kpis.docs_pending} color="#f59e0b" icon="warn" />
        <MetricCard label="CDD Awaiting Screening" value={kpis.cdd_awaiting_screening} color="#8b5cf6" icon="cdd" />
        <MetricCard label="Invoices Unpaid" value={kpis.invoices_unpaid} color="#ef4444" icon="reports" />
        <MetricCard label="Renewals Due (60d)" value={kpis.upcoming_compliance_60d} color="#10b981" icon="compliance" />
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Cases by Stage</h3>
        <ResponsiveContainer width="100%" height={200}>
          <FunnelChart>
            <Tooltip content={<CustomTooltip />} />
            <Funnel dataKey="value" data={funnelData} isAnimationActive>
              <LabelList position="right" fill="#374151" stroke="none" fontSize={10} dataKey="name" />
            </Funnel>
          </FunnelChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-700">Portfolio by RM / Ops</h3>
          <span className="text-xs text-gray-400">Click a name to expand their companies</span>
        </div>
        <div className="space-y-2">
          {(data.rm_ops_performance || []).length === 0 && (
            <p className="text-xs text-gray-400 text-center py-4">No RM/Ops users yet.</p>
          )}
          {(data.rm_ops_performance || []).map((r) => {
            const isOpen = !collapsed[r.user_id]; // default expanded
            return (
              <div key={r.user_id} className="border border-gray-100 rounded-lg overflow-hidden">
                <button
                  onClick={() => toggle(r.user_id)}
                  className="w-full flex items-center justify-between px-3 py-2.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 text-xs w-3 inline-block">{isOpen ? "▾" : "▸"}</span>
                    <span className="text-sm font-medium text-gray-800">{r.name}</span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-gray-200 text-gray-600">{r.role.toUpperCase()}</span>
                  </div>
                  <span className="text-xs text-gray-500">{r.total_cases} compan{r.total_cases === 1 ? "y" : "ies"} · {r.active_cases} in onboarding</span>
                </button>
                {isOpen && (
                  <div className="divide-y divide-gray-50">
                    {r.cases.length === 0 && (
                      <p className="text-xs text-gray-400 text-center py-3">No companies assigned yet.</p>
                    )}
                    {r.cases.map((c) => (
                      <div key={c.case_id} className="flex items-center justify-between px-3 py-2 pl-8 hover:bg-gray-50">
                        <div className="min-w-0">
                          <div className="text-xs font-medium text-gray-800 truncate">{c.company_name}</div>
                          <div className="text-xs text-gray-400">{c.case_uid}</div>
                        </div>
                        <div className="flex gap-1.5 flex-shrink-0 ml-2">
                          <Badge text={c.stage} />
                          <Badge text={c.status} />
                          <Badge text={c.invoice_status} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Docs Pending</h3>
          <div className="space-y-2">
            {data.docs_pending.length === 0 && <p className="text-xs text-gray-400">Nothing overdue.</p>}
            {data.docs_pending.map((d) => (
              <div key={d.case_id} className="flex items-center justify-between text-xs">
                <span className="text-gray-700 truncate">{d.company_name}</span>
                <span className="text-amber-600 font-medium whitespace-nowrap ml-2">{d.business_days_pending}d</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">CDD Awaiting Screening</h3>
          <div className="space-y-2">
            {data.cdd_awaiting_screening.length === 0 && <p className="text-xs text-gray-400">Queue is clear.</p>}
            {data.cdd_awaiting_screening.map((d) => (
              <div key={d.case_id} className="flex items-center justify-between text-xs">
                <span className="text-gray-700 truncate">{d.company_name}</span>
                <span className="text-purple-600 font-medium whitespace-nowrap ml-2">{d.days_waiting}d</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Invoices Unpaid</h3>
          <div className="space-y-2">
            {data.invoices_unpaid.length === 0 && <p className="text-xs text-gray-400">No outstanding invoices.</p>}
            {data.invoices_unpaid.map((d) => (
              <div key={d.case_id} className="flex items-center justify-between text-xs">
                <span className="text-gray-700 truncate">{d.company_name}</span>
                <span className="text-red-600 font-medium whitespace-nowrap ml-2">{fmt(d.invoice_amount)} · {d.days_aging}d</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Upcoming Renewals & Filings (next 60 days)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Company</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Item</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Due Date</th>
                <th className="text-right py-2 px-3 text-xs font-semibold text-gray-500">Days Left</th>
              </tr>
            </thead>
            <tbody>
              {data.upcoming_compliance.length === 0 && (
                <tr><td colSpan={4} className="text-center py-6 text-xs text-gray-400">Nothing due in the next 60 days.</td></tr>
              )}
              {data.upcoming_compliance.map((c, i) => (
                <tr key={`${c.case_id}-${c.item}-${i}`} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 text-xs font-medium text-gray-800">{c.company_name}</td>
                  <td className="py-2 px-3 text-xs text-gray-600">{c.item.replace("_", " ")}</td>
                  <td className="py-2 px-3 text-xs text-gray-600">{c.due_date}</td>
                  <td className="py-2 px-3 text-xs text-right text-gray-600">{c.days_remaining}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
