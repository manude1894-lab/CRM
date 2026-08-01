import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { dashboardApi, reportsApi } from "../api/endpoints";
import { MetricCard, CustomTooltip, Badge, Icon, Spinner, ErrorBanner } from "../components/ui";

const REPORT_TYPES = [
  { id: "case-stage-summary", title: "Case Stage Summary", desc: "Pipeline overview + stage breakdown + upcoming compliance" },
  { id: "case-details", title: "Case Details", desc: "Every case with stage, status, invoice status and RM" },
  { id: "compliance-calendar", title: "Compliance Calendar", desc: "Upcoming renewals, compliance filings and tax filings" },
  { id: "rm-ops-performance", title: "RM / Ops Performance", desc: "Caseload by Relationship Manager and Ops" },
];

export default function ReportsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      setData(await dashboardApi.get());
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load reports");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const download = async (type) => {
    setDownloading(type);
    try {
      await reportsApi.download(type);
    } catch (e) {
      alert(e.response?.data?.detail || "Download failed");
    } finally {
      setDownloading(null);
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  const kpis = data.kpis || {};
  const rmOps = data.rm_ops_performance || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Reports & Analytics</h1>
        <p className="text-sm text-gray-500">DIFC client onboarding · Download PDFs or view inline analytics</p>
      </div>

      {/* PDF Downloads */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {REPORT_TYPES.map((r) => (
          <div key={r.id} className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm flex items-center justify-between gap-4">
            <div className="flex items-start gap-3 min-w-0">
              <div className="p-2 rounded-lg text-white flex-shrink-0" style={{ background: "#2B6D9A" }}>
                <Icon name="reports" size={18} />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-gray-800">{r.title}</h3>
                <p className="text-xs text-gray-500 mt-0.5">{r.desc}</p>
              </div>
            </div>
            <button onClick={() => download(r.id)} disabled={downloading === r.id}
              className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-700 flex items-center gap-1 flex-shrink-0 disabled:opacity-60">
              <Icon name="download" size={13} />
              {downloading === r.id ? "..." : "PDF"}
            </button>
          </div>
        ))}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Open Cases" value={kpis.open_cases} color="#2B6D9A" />
        <MetricCard label="Docs Pending" value={kpis.docs_pending} color="#f59e0b" />
        <MetricCard label="CDD Awaiting Screening" value={kpis.cdd_awaiting_screening} color="#8b5cf6" />
        <MetricCard label="Invoices Unpaid" value={kpis.invoices_unpaid} color="#ef4444" />
      </div>

      {/* Stage Breakdown */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">Cases by Stage</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-500">Stage</th>
                <th className="text-right py-2 px-3 text-xs font-semibold text-gray-500">Cases</th>
              </tr>
            </thead>
            <tbody>
              {(data.stage_breakdown || []).filter((s) => s.count > 0).map((s) => (
                <tr key={s.stage} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3"><Badge text={s.stage} /></td>
                  <td className="py-2 px-3 text-xs text-right text-gray-600">{s.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* RM / Ops Performance */}
      <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">RM / Ops Performance</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={rmOps} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="total_cases" name="Total Cases" fill="#2B6D9A" radius={[4, 4, 0, 0]} />
            <Bar dataKey="active_cases" name="Active Cases" fill="#10b981" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {rmOps.map((r) => (
            <div key={r.user_id} className="bg-gray-50 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center" style={{ background: "#2B6D9A" }}>
                  {r.name.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                </div>
                <span className="font-semibold text-sm text-gray-800">{r.name}</span>
                <Badge text={r.role} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-gray-500">Total Cases</span><br /><span className="font-bold text-gray-800">{r.total_cases}</span></div>
                <div><span className="text-gray-500">Active Cases</span><br /><span className="font-bold text-gray-800">{r.active_cases}</span></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Upcoming Compliance */}
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
              {(data.upcoming_compliance || []).map((c, i) => (
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
