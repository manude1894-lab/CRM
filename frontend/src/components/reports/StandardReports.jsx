import React, { useEffect, useState } from "react";
import { departmentsApi, reportsApi, usersApi } from "../../api/endpoints";
import { useMasters } from "../../hooks/useMasters";
import { Button, DateInput, Field, Input, Select, Spinner } from "../ui";
import { fmtDate } from "../../utils/constants";
import { toast } from "../../store/toast";
import { useAuthStore } from "../../store/auth";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const show = (v) => (typeof v === "string" && ISO_DATE.test(v) ? fmtDate(v) : v ?? "—");
// Which inputs each report takes (Triam UAT 18-11-2026: the user picks the days, the dates and the status).
const TAKES_DAYS = { "documents-expiring": "Within (days)", "aml-reviews-due": "Due within (days)",
  "under-formation": "Pending at least (days, 0 = all)" };
// Triam UAT 19-11-2026: the amendments, invoice and service request reports filter by Triam Anchor Entity,
// Department, Client Tag, Anchor RM and date range (plus request type / service request type).
const CLIENT_FILTERS = ["amendments", "invoices-onboarding", "invoices-service-requests", "invoices-pending", "service-requests-ageing"];
const TAKES_DATES = ["prospects-assigned", "onboarding-approved", "onboarding-in-progress", ...CLIENT_FILTERS];
const BY_DEPARTMENT = ["onboarding-approved", "onboarding-in-progress", ...CLIENT_FILTERS];
const REQUEST_TYPES = ["Onboarding", "Service Request"];
// The side list's groups, in this order; a report not listed here goes under "Other".
const GROUPS = [
  ["Onboarding", ["onboarding-approved", "onboarding-in-progress", "under-formation", "rejected-with-rm"]],
  ["Compliance & KYC", ["clients-risk", "aml-reviews-due", "aml-reviews-expired", "amendments"]],
  ["Documents", ["documents-expiring", "documents-expired"]],
  ["Prospects", ["prospects-assigned", "prospects-unassigned"]],
  ["Finance & service requests", ["invoices-onboarding", "invoices-service-requests", "invoices-pending", "service-requests-ageing"]],
];
const groupReports = (list) => {
  const placed = new Set(GROUPS.flatMap(([, keys]) => keys));
  return [...GROUPS.map(([g, keys]) => [g, keys.map((k) => list.find((r) => r.key === k)).filter(Boolean)]),
    ["Other", list.filter((r) => !placed.has(r.key))]].filter(([, reports]) => reports.length);
};

/** BRD §20a — the standard reports, shown on screen and downloaded as Excel or PDF by the users the
 * Administrator allows (Triam UAT 19-11-2026). */
export default function StandardReports() {
  const canExport = useAuthStore((s) => s.can("report.export"));
  const [exporting, setExporting] = useState(null);
  const [list, setList] = useState([]);
  const [key, setKey] = useState("onboarding-in-progress");
  const [params, setParams] = useState({ days: 30, date_from: "", date_to: "", status: "", department_id: "",
    entity: "", tag: "", rm_id: "", request_type: "", sr_type: "" });
  const [statuses, setStatuses] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [rms, setRms] = useState([]);
  const entities = useMasters("triam_entity", []);
  const tags = useMasters("tag", []);
  const srTypes = useMasters("service_request_type", []);
  const setParam = (k) => (e) => setParams((p) => ({ ...p, [k]: e.target.value }));
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    reportsApi.standardList().then(setList).catch(() => setList([]));
    reportsApi.onboardingStatuses().then(setStatuses).catch(() => setStatuses([]));
    departmentsApi.list().then((d) => setDepartments(d.filter((x) => x.is_active !== false))).catch(() => setDepartments([]));
    usersApi.list().then((u) => setRms(u.filter((x) => x.is_active && x.handles_clients && x.role !== "admin" && !x.person_id)
      .sort((a, b) => a.name.localeCompare(b.name)))).catch(() => setRms([]));
  }, []);
  const paramsFor = (k) => {
    const p = {};
    if (TAKES_DAYS[k]) p.days = params.days === "" ? 30 : params.days;
    if (TAKES_DATES.includes(k)) Object.assign(p, { date_from: params.date_from || undefined, date_to: params.date_to || undefined });
    if (k === "onboarding-in-progress" && params.status) p.status = params.status;
    if (BY_DEPARTMENT.includes(k) && params.department_id) p.department_id = params.department_id;
    if (CLIENT_FILTERS.includes(k)) {
      for (const f of ["entity", "tag", "rm_id"]) if (params[f]) p[f] = params[f];
      if (k === "invoices-pending" && params.request_type) p.request_type = params.request_type;
      if (k === "service-requests-ageing" && params.sr_type) p.sr_type = params.sr_type;
    }
    return p;
  };
  const run = async (k = key) => {
    setBusy(true);
    try {
      setReport(await reportsApi.standard(k, paramsFor(k)));
    } catch (e) { toast.error(e.response?.data?.detail || "Could not run the report"); } finally { setBusy(false); }
  };

  // The server builds the file from the same report and records the download in the audit log.
  const download = async (format) => {
    setExporting(format);
    try {
      const r = await reportsApi.exportFile(key, paramsFor(key), format);
      const name = /filename="([^"]+)"/.exec(r.headers?.["content-disposition"] || "")?.[1] || `report.${format}`;
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data);
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    } catch (e) {
      let detail = "Could not download the report";
      try { detail = JSON.parse(await e.response.data.text()).detail || detail; } catch { /* not a JSON error */ }
      toast.error(detail);
    } finally { setExporting(null); }
  };
  useEffect(() => { run(key); }, [key]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[250px_minmax(0,1fr)] gap-4 items-start">
      {/* Triam 22-11-2026 design refresh: the reports grouped down the side instead of a wall of pills. */}
      <nav aria-label="Reports" className="bg-white border border-gray-200/70 rounded-xl shadow-[0_1px_2px_rgba(16,24,40,0.04)] p-2 lg:sticky lg:top-0">
        {groupReports(list).map(([group, reports]) => (
          <div key={group} className="mb-1">
            <div className="px-2.5 pt-2.5 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-gray-500">{group}</div>
            {reports.map((r) => (
              <button key={r.key} onClick={() => setKey(r.key)} aria-current={key === r.key ? "page" : undefined}
                className={`relative w-full text-left px-2.5 py-1.5 rounded-lg text-[13px] leading-snug ${key === r.key
                  ? "bg-brand-50 text-brand-700 font-semibold" : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"}`}>
                {key === r.key && <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-gold" />}
                {r.title}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <div className="bg-white border border-gray-200/70 rounded-xl shadow-[0_1px_2px_rgba(16,24,40,0.04)] min-w-0">
      <div className="px-4 pt-4 pb-1 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">{list.find((r) => r.key === key)?.title || "Report"}</h2>
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
          {CLIENT_FILTERS.includes(key) && (
            <>
              <div className="w-44"><Field label="Triam Anchor Entity"><Select value={params.entity} onChange={setParam("entity")}>
                <option value="">All</option>
                {entities.items.map((i) => <option key={i.code} value={i.code}>{i.label}</option>)}
              </Select></Field></div>
              <div className="w-44"><Field label="Client Tag"><Select value={params.tag} onChange={setParam("tag")}>
                <option value="">All</option>
                {tags.items.map((i) => <option key={i.code} value={i.code}>{i.label}</option>)}
              </Select></Field></div>
              <div className="w-48"><Field label="Anchor RM"><Select value={params.rm_id} onChange={setParam("rm_id")}>
                <option value="">All</option>
                {rms.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </Select></Field></div>
            </>
          )}
          {key === "invoices-pending" && (
            <div className="w-44"><Field label="Request Type"><Select value={params.request_type} onChange={setParam("request_type")}>
              <option value="">All</option>
              {REQUEST_TYPES.map((t) => <option key={t}>{t}</option>)}
            </Select></Field></div>
          )}
          {key === "service-requests-ageing" && (
            <div className="w-56"><Field label="Service Request Type"><Select value={params.sr_type} onChange={setParam("sr_type")}>
              <option value="">All</option>
              {srTypes.items.map((i) => <option key={i.code} value={i.code}>{i.label}</option>)}
            </Select></Field></div>
          )}
          {(TAKES_DAYS[key] || TAKES_DATES.includes(key) || BY_DEPARTMENT.includes(key)) && <div className="mb-4"><Button onClick={() => run()}>Run</Button></div>}
          {canExport && (
            <div className="mb-4 ml-auto flex gap-2">
              <Button onClick={() => download("xlsx")} disabled={!report || !!exporting}>{exporting === "xlsx" ? "Preparing…" : "Excel"}</Button>
              <Button onClick={() => download("pdf")} disabled={!report || !!exporting}>{exporting === "pdf" ? "Preparing…" : "PDF"}</Button>
            </div>
          )}
        </div>
        {busy || !report ? <Spinner /> : (
          <>
            <div className="text-xs text-gray-500 mb-2">{report.title} · {report.rows.length} row{report.rows.length === 1 ? "" : "s"}</div>
            {report.rows.length === 0 ? <p className="text-sm text-gray-500 py-6 text-center">Nothing to report.</p> : (
              <div className="overflow-x-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 rounded" tabIndex={0} role="region" aria-label="Report table">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                    {/* Review 22-11-2026: the first column (the client) stays in view while scrolling a wide report. */}
                    {report.columns.map((c, j) => <th key={c} className={`text-left py-2 px-3 font-semibold whitespace-nowrap ${j === 0 ? "sticky left-0 z-[1] bg-gray-50 shadow-[1px_0_0_#f3f4f6]" : ""}`}>{c}</th>)}
                  </tr></thead>
                  <tbody>
                    {report.rows.map((r, i) => (
                      <tr key={i} className="border-b border-gray-50">{r.map((v, j) => <td key={j} className={`py-2 px-3 text-xs text-gray-700 ${j === 0 ? "sticky left-0 bg-white font-medium text-gray-800 shadow-[1px_0_0_#f3f4f6]" : ""}`}>{show(v)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
      </div>
    </div>
  );
}
