import React, { useEffect, useState } from "react";
import { departmentsApi, reportsApi } from "../../api/endpoints";
import { Button, DateInput, Field, Input, Select, Spinner } from "../ui";
import { csvDate, exportFilename, fmtDate } from "../../utils/constants";
import { toast } from "../../store/toast";
import { useAuthStore } from "../../store/auth";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const show = (v) => (typeof v === "string" && ISO_DATE.test(v) ? fmtDate(v) : v ?? "—");
// Which inputs each report takes (Triam UAT 18-11-2026: the user picks the days, the dates and the status).
const TAKES_DAYS = { "documents-expiring": "Within (days)", "aml-reviews-due": "Due within (days)",
  "under-formation": "Pending at least (days, 0 = all)" };
const TAKES_DATES = ["prospects-assigned", "onboarding-approved", "onboarding-in-progress"];
const BY_DEPARTMENT = ["onboarding-approved", "onboarding-in-progress"];

/** BRD §20a — the standard reports, shown on screen and exported to CSV. */
export default function StandardReports() {
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [list, setList] = useState([]);
  const [key, setKey] = useState("onboarding-in-progress");
  const [params, setParams] = useState({ days: 30, date_from: "", date_to: "", status: "", department_id: "" });
  const [statuses, setStatuses] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    reportsApi.standardList().then(setList).catch(() => setList([]));
    reportsApi.onboardingStatuses().then(setStatuses).catch(() => setStatuses([]));
    departmentsApi.list().then((d) => setDepartments(d.filter((x) => x.is_active !== false))).catch(() => setDepartments([]));
  }, []);
  const run = async (k = key) => {
    setBusy(true);
    try {
      const p = {};
      if (TAKES_DAYS[k]) p.days = params.days === "" ? 30 : params.days;
      if (TAKES_DATES.includes(k)) Object.assign(p, { date_from: params.date_from || undefined, date_to: params.date_to || undefined });
      if (k === "onboarding-in-progress" && params.status) p.status = params.status;
      if (BY_DEPARTMENT.includes(k) && params.department_id) p.department_id = params.department_id;
      setReport(await reportsApi.standard(k, p));
    } catch (e) { toast.error(e.response?.data?.detail || "Could not run the report"); } finally { setBusy(false); }
  };
  useEffect(() => { run(key); }, [key]);

  const exportCsv = () => {
    if (!report) return;
    const lines = [report.columns, ...report.rows.map((r) => r.map(csvDate))]
      .map((r) => r.map((v) => `"${(v ?? "").toString().replace(/"/g, '""')}"`).join(","));
    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = exportFilename(report.title.replace(/[^A-Za-z0-9]+/g, "-").toLowerCase(), "csv");
    a.click();
  };

  return (
    <div className="bg-white border border-gray-100 rounded-xl shadow-sm">
      <div className="px-4 py-3 border-b border-gray-100 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-gray-800">Standard reports</span>
        <div className="flex flex-wrap gap-1.5 ml-2">
          {list.map((r) => (
            <button key={r.key} onClick={() => setKey(r.key)}
              className={`px-2.5 py-1 text-xs rounded-full border ${key === r.key ? "border-brand-600 bg-brand-600 text-white" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              {r.title}
            </button>
          ))}
        </div>
      </div>
      <div className="px-4 py-3">
        <div className="flex flex-wrap items-end gap-3 mb-3">
          {TAKES_DAYS[key] && (
            <div className="w-52"><Field label={TAKES_DAYS[key]}><Input type="number" min="0" max="3650" value={params.days}
              onChange={(e) => setParams((p) => ({ ...p, days: e.target.value }))} /></Field></div>
          )}
          {TAKES_DATES.includes(key) && (
            <>
              <div className="w-44"><Field label="From"><DateInput value={params.date_from} onChange={(e) => setParams((p) => ({ ...p, date_from: e.target.value }))} /></Field></div>
              <div className="w-44"><Field label="To"><DateInput value={params.date_to} onChange={(e) => setParams((p) => ({ ...p, date_to: e.target.value }))} /></Field></div>
            </>
          )}
          {key === "onboarding-in-progress" && (
            <div className="w-56"><Field label="Status"><Select value={params.status} onChange={(e) => setParams((p) => ({ ...p, status: e.target.value }))}>
              <option value="">All not yet approved</option>
              {statuses.map((s) => <option key={s}>{s}</option>)}
            </Select></Field></div>
          )}
          {BY_DEPARTMENT.includes(key) && departments.length > 1 && (
            <div className="w-48"><Field label="Department"><Select value={params.department_id} onChange={(e) => setParams((p) => ({ ...p, department_id: e.target.value }))}>
              <option value="">All I can see</option>
              {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Select></Field></div>
          )}
          {(TAKES_DAYS[key] || TAKES_DATES.includes(key) || BY_DEPARTMENT.includes(key)) && <div className="mb-4"><Button onClick={() => run()}>Run</Button></div>}
          {isAdmin && <div className="mb-4 ml-auto"><Button onClick={exportCsv} disabled={!report?.rows?.length}>Export CSV</Button></div>}
        </div>
        {busy || !report ? <Spinner /> : (
          <>
            <div className="text-xs text-gray-500 mb-2">{report.title} · {report.rows.length} row{report.rows.length === 1 ? "" : "s"}</div>
            {report.rows.length === 0 ? <p className="text-sm text-gray-400 py-6 text-center">Nothing to report.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                    {report.columns.map((c) => <th key={c} className="text-left py-2 px-3 font-semibold">{c}</th>)}
                  </tr></thead>
                  <tbody>
                    {report.rows.map((r, i) => (
                      <tr key={i} className="border-b border-gray-50">{r.map((v, j) => <td key={j} className="py-2 px-3 text-xs text-gray-700">{show(v)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
