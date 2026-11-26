import React, { useEffect, useRef, useState } from "react";
import { accountsApi, departmentsApi, reportsApi, usersApi } from "../../api/endpoints";
import ClientPicker from "../ClientPicker";
import { useMasters } from "../../hooks/useMasters";
import { Pager, SortTh, useListView } from "../listing";
import { Button, DateInput, Field, Icon, Input, PageHeader, SearchInput, Select, Spinner } from "../ui";
import { fmtDate } from "../../utils/constants";
import { toast } from "../../store/toast";
import { saveResponse } from "../../utils/download";
import { useAuthStore } from "../../store/auth";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const show = (v) => (typeof v === "string" && ISO_DATE.test(v) ? fmtDate(v) : v === true ? "Yes" : v === false ? "No" : v ?? "—");

// Triam 22-11-2026: tidy columns. Dates and numbers stay on one line (numbers to the right); a list such as the
// services applied ("A; B; C") shows one item per line; long text wraps within a sensible width.
const isNumber = (v) => typeof v === "number";
const isShort = (v) => v == null || typeof v !== "string" || ISO_DATE.test(v) || v.length <= 14;
function Cell({ value }) {
  if (typeof value === "string" && value.includes("; ")) {
    return <ul className="space-y-0.5">{value.split("; ").map((x, i) => <li key={i} className="leading-snug">{x}</li>)}</ul>;
  }
  return show(value);
}
const cellClass = (v) => (isNumber(v) ? "text-right tabular-nums whitespace-nowrap" : isShort(v) ? "whitespace-nowrap" : "min-w-[12rem] max-w-[20rem]");
// Which inputs each report takes (Triam UAT 18-11-2026: the user picks the days, the dates and the status).
const TAKES_DAYS = { "documents-expiring": "Within (days)", "aml-reviews-due": "Due within (days)",
  "under-formation": "Pending at least (days, 0 = all)" };
// Triam UAT 19-11-2026: the amendments, invoice and service request reports filter by Triam Anchor Entity,
// Department, Client Tag, Anchor RM and date range (plus request type / service request type).
const CLIENT_FILTERS = ["amendments", "invoices-onboarding", "invoices-service-requests", "invoices-pending", "service-requests-ageing",
  "visits-recorded", "visits-not-done"];
// Triam UAT 25-11-2026: the call / visit reports also filter by client, and not by department.
const BY_CLIENT = ["visits-recorded", "visits-not-done"];
const TAKES_DATES = ["prospects-assigned", "onboarding-approved", "onboarding-in-progress", ...CLIENT_FILTERS];
const BY_DEPARTMENT = ["onboarding-approved", "onboarding-in-progress", ...CLIENT_FILTERS.filter((k) => !BY_CLIENT.includes(k))];
const REQUEST_TYPES = ["Onboarding", "Service Request"];
// The side list's groups, in this order; a report not listed here goes under "Other".
const GROUPS = [
  ["Onboarding", ["onboarding-approved", "onboarding-in-progress", "under-formation", "rejected-with-rm"]],
  ["Compliance & KYC", ["clients-risk", "aml-reviews-due", "aml-reviews-expired", "amendments", "data-quality"]],
  ["Documents", ["documents-expiring", "documents-expired"]],
  ["Calls & visits", ["visits-recorded", "visits-not-done"]],
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
/**
 * Triam 24-11-2026: a wide report scrolls sideways inside a box of fixed height, so its scrollbar is always in view
 * (not below the last row); the headings stay at the top; a fade at the edge shows that more columns are there.
 */
function useSideScroll(deps) {
  const ref = useRef(null);
  const [edges, setEdges] = useState({ more: false, left: false, right: false });
  const [height, setHeight] = useState(null);
  // The box ends at the bottom of the window, so its sideways scrollbar is on screen without scrolling the page.
  const fit = () => {
    const el = ref.current;
    if (el) setHeight(Math.max(320, Math.round(window.innerHeight - el.getBoundingClientRect().top - 16)));
  };
  const measure = () => {
    const el = ref.current;
    if (!el) return;
    const more = el.scrollWidth > el.clientWidth + 2;
    setEdges({ more, left: more && el.scrollLeft > 2, right: more && el.scrollLeft + el.clientWidth < el.scrollWidth - 2 });
  };
  useEffect(() => {
    measure(); fit();
    window.addEventListener("resize", fit);
    const el = ref.current;
    const ro = el && typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    if (ro) ro.observe(el);
    return () => { window.removeEventListener("resize", fit); if (ro) ro.disconnect(); };
  }, deps);
  return { ref, edges, measure, height };
}

export default function StandardReports() {
  const canExport = useAuthStore((s) => s.can("report.export"));
  const [exporting, setExporting] = useState(null);
  const [list, setList] = useState([]);
  // Triam 26-11-2026: like other CRMs, a reports home (the list) and a full-width view of one report.
  const [key, setKey] = useState(null);
  const [find, setFind] = useState("");
  const [params, setParams] = useState({ days: 30, date_from: "", date_to: "", status: "", department_id: "",
    entity: "", tag: "", rm_id: "", request_type: "", sr_type: "", account_id: "" });
  const [clients, setClients] = useState([]);
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
    accountsApi.list({ limit: 1000 }).then((r) => setClients(r.items || [])).catch(() => setClients([]));
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
      if (BY_CLIENT.includes(k) && params.account_id) p.account_id = params.account_id;
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
      saveResponse(await reportsApi.exportFile(key, paramsFor(key), format), `triam-${key}.${format}`);
    } catch (e) {
      let detail = "Could not download the report";
      try { detail = JSON.parse(await e.response.data.text()).detail || detail; } catch { /* not a JSON error */ }
      toast.error(detail);
    } finally { setExporting(null); }
  };
  useEffect(() => { if (key) run(key); else setReport(null); }, [key]);
  const side = useSideScroll([report, busy]);
  const view = useListView(report?.rows || [], { key: "reports", defaultSize: 50, valueOf: (r, j) => r[j], resetOn: [report] });
  useEffect(() => { view.setSort(null); }, [report?.title]);

  // The reports home: every report in its group, with a search.
  if (!key) {
    const q = find.trim().toLowerCase();
    const groups = groupReports(list).map(([g, rs]) => [g, rs.filter((r) => !q || r.title.toLowerCase().includes(q))])
      .filter(([, rs]) => rs.length);
    return (
      <div className="space-y-5">
        <PageHeader title="Reports" subtitle={`${list.length} reports`} />
        <div className="max-w-md"><SearchInput value={find} onChange={setFind} placeholder="Search reports…" /></div>
        {groups.length === 0 && <p className="text-sm text-gray-500">No report matches.</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 items-start">
          {groups.map(([group, reports]) => (
            <section key={group} className="bg-white border border-gray-200/70 rounded-xl shadow-[0_1px_2px_rgba(16,24,40,0.04)]">
              <h2 className="px-4 pt-3.5 pb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-gray-500">{group}</h2>
              <ul className="pb-2">
                {reports.map((r) => (
                  <li key={r.key}>
                    <button type="button" onClick={() => setKey(r.key)}
                      className="group w-full flex items-center justify-between gap-3 px-4 py-2 text-left text-sm text-gray-800 hover:bg-brand-50/60 hover:text-brand-700">
                      <span>{r.title}</span>
                      <Icon name="chevronRight" size={15} className="flex-shrink-0 text-gray-300 group-hover:text-brand-500" />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    );
  }

  const title = list.find((r) => r.key === key)?.title || "Report";
  const period = report?.title.match(/\(([^)]*)\)$/)?.[1]; // e.g. "all time" or "01 11 2026 to 26 11 2026"
  return (
    <div className="space-y-4">
      <PageHeader title={title} back={{ label: "Reports", onClick: () => setKey(null) }}
        actions={canExport && (
          <>
            <Button onClick={() => download("xlsx")} disabled={!report || !!exporting}><Icon name="download" size={14} /> {exporting === "xlsx" ? "Preparing…" : "Excel"}</Button>
            <Button onClick={() => download("pdf")} disabled={!report || !!exporting}><Icon name="download" size={14} /> {exporting === "pdf" ? "Preparing…" : "PDF"}</Button>
          </>
        )} />
      <div className="bg-white border border-gray-200/70 rounded-xl shadow-[0_1px_2px_rgba(16,24,40,0.04)] min-w-0">
      <div className="px-4 py-3">
        <div className="flex flex-wrap items-end gap-x-3 -mx-4 -mt-3 mb-3 px-4 pt-3 border-b border-gray-100 bg-gray-50/60 rounded-t-xl empty:hidden">
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
          {BY_CLIENT.includes(key) && (
            <div className="w-64"><Field label="Client"><ClientPicker clients={clients} allLabel="All clients" value={params.account_id}
              onChange={(v) => setParams((p) => ({ ...p, account_id: v }))} /></Field></div>
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
        </div>
        {busy || !report ? <Spinner /> : (
          <>
            <div className="text-xs text-gray-500 mb-2">{report.rows.length} row{report.rows.length === 1 ? "" : "s"}{period ? ` · ${period}` : ""}</div>
            {report.rows.length === 0 ? <p className="text-sm text-gray-500 py-6 text-center">Nothing to report.</p> : (
              <>
              <div className="relative">
              {side.edges.right && <div aria-hidden="true" className="pointer-events-none absolute top-0 right-0 bottom-3 w-10 z-[4] bg-gradient-to-l from-white to-transparent" />}
              <div ref={side.ref} onScroll={side.measure} style={side.height ? { maxHeight: side.height } : undefined}
                className="report-scroll max-h-[70vh] overflow-auto border border-gray-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 rounded" tabIndex={0} role="region" aria-label="Report table">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                    {/* Review 22-11-2026: the first column (the client) stays in view while scrolling a wide report. */}
                    {report.columns.map((c, j) => <SortTh key={c} label={c} by={j} sort={view.sort} onSort={view.setSort}
                      className={`py-2 align-bottom sticky top-0 bg-gray-50 shadow-[0_1px_0_#e5e7eb] ${isNumber(report.rows[0]?.[j]) ? "text-right" : ""} ${j === 0 ? "left-0 z-[3] shadow-[1px_1px_0_#e5e7eb]" : "z-[2]"}`} />)}
                  </tr></thead>
                  <tbody>
                    {view.rows.map((r, i) => (
                      <tr key={i} className="border-b border-gray-50 align-top hover:bg-gray-50/60">{r.map((v, j) => <td key={j} className={`py-2 px-3 text-xs text-gray-700 ${cellClass(v)} ${j === 0 ? "sticky left-0 z-[1] bg-white font-medium text-gray-800 shadow-[1px_0_0_#f3f4f6] min-w-[9rem]" : ""}`}><Cell value={v} /></td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </div>
              </>
            )}
            {report.rows.length > 0 && <div className="mt-3"><Pager {...view.pager} label="Rows" /></div>}
          </>
        )}
      </div>
      </div>
    </div>
  );
}
