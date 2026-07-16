import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  Funnel, FunnelChart, LabelList,
} from "recharts";
import { dashboardApi } from "../api/endpoints";
import { MetricCard, CustomTooltip, Spinner, ErrorBanner } from "../components/ui";
import { PIE_COLORS, fmt } from "../utils/constants";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

  const rmOpsData = (data.rm_ops_performance || []).map((r) => ({ name: r.name, total: r.total_cases, active: r.active_cases }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Onboarding Dashboard</h1>
        <p className="text-sm text-gray-500">DIFC client onboarding & compliance · real-time pipeline overview</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard label="Open Cases" value={kpis.open_cases} icon="cases" />
        <MetricCard label="Docs Pending" value={kpis.docs_pending} color="#f59e0b" icon="warn" />
        <MetricCard label="CDD Awaiting Screening" value={kpis.cdd_awaiting_screening} color="#8b5cf6" icon="cdd" />
        <MetricCard label="Invoices Unpaid" value={kpis.invoices_unpaid} color="#ef4444" icon="reports" />
        <MetricCard label="Renewals Due (60d)" value={kpis.upcoming_compliance_60d} color="#10b981" icon="compliance" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Cases by Stage</h3>
          <ResponsiveContainer width="100%" height={240}>
            <FunnelChart>
              <Tooltip content={<CustomTooltip />} />
              <Funnel dataKey="value" data={funnelData} isAnimationActive>
                <LabelList position="right" fill="#374151" stroke="none" fontSize={10} dataKey="name" />
              </Funnel>
            </FunnelChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Caseload by RM / Ops</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={rmOpsData} margin={{ top: 5, right: 10, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="total" name="Total Cases" fill="#2B6D9A" radius={[4, 4, 0, 0]} />
              <Bar dataKey="active" name="Active Cases" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
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
