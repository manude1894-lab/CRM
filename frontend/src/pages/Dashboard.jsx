import React, { useEffect, useState } from "react";
import { dashboardApi, accountsApi } from "../api/endpoints";
import { Icon, Badge, Spinner, ErrorBanner } from "../components/ui";
import { fmt, fmtDate } from "../utils/constants";
import { useAuthStore } from "../store/auth";

const DUE_SOON_DAYS = 60;
const REFRESH_MS = 5 * 60 * 1000;

// Client-level expiry dates surfaced in "Due soon", alongside the per-case filings.
const ACCOUNT_DUE_FIELDS = [
  ["license_expiry_date", "Licence expiry"],
  ["next_aml_review_date", "AML review"],
  ["engagement_letter_valid_until", "Engagement letter"],
  ["uae_visa_expiry", "UAE visa expiry"],
  ["passport_expiry_date", "Passport expiry"],
];
const FILING_LABEL = { renewal: "Licence renewal", esr_filing: "ESR filing", ar_filing: "Annual Return", bo_filing: "ROM/RBO filing" };

const daysUntil = (iso) => Math.round((new Date(iso) - new Date(new Date().toDateString())) / 86400000);

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

function StatCard({ label, value, hint, attention, icon, onClick }) {
  const hot = attention && value > 0;
  return (
    <button onClick={onClick}
      className="text-left bg-white rounded-xl border border-gray-200/70 px-4 py-3.5 hover:border-brand-200 hover:shadow-sm transition-all group">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-gray-500 truncate">{label}</span>
        <Icon name={icon} size={16} className="text-gray-300 group-hover:text-brand-500 flex-shrink-0" />
      </div>
      <div className="text-2xl font-bold text-gray-900 mt-1 tabular-nums">{value}</div>
      <div className={`text-[11px] mt-0.5 ${hot ? "text-amber-600 font-medium" : "text-gray-400"}`}>
        {hot ? hint : value > 0 ? "View" : "All clear"}
      </div>
    </button>
  );
}

function Panel({ title, right, children }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200/70">
      <header className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        {right}
      </header>
      {children}
    </section>
  );
}

function EmptyState({ text }) {
  return (
    <div className="flex items-center gap-2 px-4 py-6 text-sm text-gray-400">
      <span className="w-6 h-6 rounded-full bg-emerald-50 text-emerald-500 flex items-center justify-center"><Icon name="check" size={14} /></span>
      {text}
    </div>
  );
}

function Pipeline({ stages, onStage }) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-[880px]">
        {stages.map((s, i) => {
          const busy = s.count > 0;
          return (
            <button key={s.stage} onClick={() => onStage(s.stage)} title={`${s.stage}: ${s.count}`}
              className="flex-1 min-w-0 relative group px-1 pt-3 pb-3 flex flex-col items-center justify-start text-center">
              {/* connector line behind the dots */}
              <span className={`absolute top-[26px] h-0.5 bg-gray-200 ${i === 0 ? "left-1/2 right-0" : i === stages.length - 1 ? "left-0 right-1/2" : "left-0 right-0"}`} />
              <span className={`relative mx-auto flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold tabular-nums transition-colors
                ${busy ? "bg-brand-600 text-white ring-4 ring-brand-50" : "bg-white text-gray-400 border border-gray-200 group-hover:border-brand-300"}`}>
                {s.count}
              </span>
              <span className={`block mt-2 text-[11px] leading-tight ${busy ? "text-gray-800 font-medium" : "text-gray-400"}`}>{s.stage}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function Dashboard({ onNavigate = () => {} } = {}) {
  const user = useAuthStore((s) => s.user);
  const [data, setData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [open, setOpen] = useState({});
  const [showAllDue, setShowAllDue] = useState(false);

  const load = async () => {
    try {
      setError(null);
      const [dash, accs] = await Promise.all([dashboardApi.get(), accountsApi.list({ limit: 200 }).catch(() => [])]);
      setData(dash);
      setAccounts(Array.isArray(accs?.items) ? accs.items : []); // paginated: { items, total }
      setUpdatedAt(new Date());
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => clearInterval(t);
  }, []);

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!data) return null;

  const kpis = data.kpis;

  // Action needed: one list across the three work queues, oldest first.
  const actions = [
    ...data.docs_pending.map((d) => ({ key: `d${d.case_id}`, caseId: d.case_id, company: d.company_name, what: "Documents pending", days: d.business_days_pending, tone: "amber" })),
    ...data.cdd_awaiting_screening.map((d) => ({ key: `c${d.case_id}`, caseId: d.case_id, company: d.company_name, what: "Awaiting CDD screening", days: d.days_waiting, tone: "violet" })),
    ...data.invoices_unpaid.map((d) => ({ key: `i${d.case_id}`, caseId: d.case_id, company: d.company_name, what: `Invoice unpaid · ${fmt(d.invoice_amount)}`, days: d.days_aging, tone: "red" })),
  ].sort((a, b) => b.days - a.days);

  // Due soon: case filings + client-level expiries, overdue first.
  const due = [
    ...data.upcoming_compliance.map((c) => ({
      key: `f${c.case_id}-${c.item}`, company: c.company_name, what: FILING_LABEL[c.item] || c.item.replace(/_/g, " "),
      date: c.due_date, days: c.days_remaining, go: () => onNavigate({ page: "compliance" }),
    })),
    ...accounts.flatMap((a) => ACCOUNT_DUE_FIELDS
      .filter(([f]) => a[f] && daysUntil(a[f]) <= DUE_SOON_DAYS)
      .map(([f, what]) => ({
        key: `a${a.id}-${f}`, company: a.company_name, what, date: a[f], days: daysUntil(a[f]),
        go: () => onNavigate({ page: "accounts", accountId: a.id }),
      }))),
  ].sort((a, b) => a.days - b.days);
  const dueShown = showAllDue ? due : due.slice(0, 8);

  const toneDot = { amber: "bg-amber-400", violet: "bg-violet-400", red: "bg-red-400" };
  const people = data.rm_ops_performance || [];
  const maxCases = Math.max(1, ...people.map((p) => p.total_cases));

  return (
    <div className="max-w-[1400px] mx-auto space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{greeting()}{user?.name ? `, ${user.name.split(" ")[0]}` : ""}</h1>
          <p className="text-sm text-gray-500">Here's what needs attention across onboarding and compliance.</p>
        </div>
        <button onClick={load} className="text-xs text-gray-400 hover:text-brand-600">
          Updated {updatedAt?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard label="Open cases" value={kpis.open_cases} icon="cases" onClick={() => onNavigate({ page: "cases" })} />
        <StatCard label="Documents pending" value={kpis.docs_pending} attention hint="Chase clients" icon="warn" onClick={() => onNavigate({ page: "cases", stage: "Docs Requested" })} />
        <StatCard label="Awaiting screening" value={kpis.cdd_awaiting_screening} attention hint="Screening queue" icon="cdd" onClick={() => onNavigate({ page: "cdd" })} />
        <StatCard label="Unpaid invoices" value={kpis.invoices_unpaid} attention hint="Follow up payment" icon="invoices" onClick={() => onNavigate({ page: "invoices" })} />
        <StatCard label={`Due in ${DUE_SOON_DAYS} days`} value={due.length} attention hint="See due soon" icon="compliance" onClick={() => onNavigate({ page: "compliance" })} />
      </div>

      <Panel title="Onboarding pipeline" right={<span className="text-xs text-gray-400">Click a stage to open those cases</span>}>
        <div className="px-3 py-2">
          <Pipeline stages={data.stage_breakdown || []} onStage={(stage) => onNavigate({ page: "cases", stage })} />
        </div>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel title="Action needed" right={actions.length > 0 && <span className="text-xs font-medium text-gray-500">{actions.length}</span>}>
          {actions.length === 0 ? <EmptyState text="Nothing waiting. All queues are clear." /> : (
            <ul className="divide-y divide-gray-50 max-h-80 overflow-y-auto">
              {actions.map((a) => (
                <li key={a.key}>
                  <button onClick={() => onNavigate({ page: "cases", caseId: a.caseId })}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${toneDot[a.tone]}`} />
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm font-medium text-gray-800 truncate">{a.company}</span>
                      <span className="block text-xs text-gray-500">{a.what}</span>
                    </span>
                    <span className="text-xs text-gray-500 tabular-nums whitespace-nowrap">{a.days}d</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title={`Due soon (next ${DUE_SOON_DAYS} days)`} right={due.length > 0 && <span className="text-xs font-medium text-gray-500">{due.length}</span>}>
          {due.length === 0 ? <EmptyState text={`Nothing due in the next ${DUE_SOON_DAYS} days.`} /> : (
            <>
              <ul className="divide-y divide-gray-50">
                {dueShown.map((d) => (
                  <li key={d.key}>
                    <button onClick={d.go} className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left">
                      <span className="flex-1 min-w-0">
                        <span className="block text-sm font-medium text-gray-800 truncate">{d.company}</span>
                        <span className="block text-xs text-gray-500">{d.what} · {fmtDate(d.date)}</span>
                      </span>
                      <span className={`text-xs font-medium whitespace-nowrap px-2 py-0.5 rounded-md tabular-nums
                        ${d.days < 0 ? "bg-red-50 text-red-600" : d.days <= 14 ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-600"}`}>
                        {d.days < 0 ? `${-d.days}d overdue` : d.days === 0 ? "Today" : `${d.days}d`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {due.length > 8 && (
                <button onClick={() => setShowAllDue((v) => !v)} className="w-full text-xs text-brand-600 hover:underline py-2 border-t border-gray-100">
                  {showAllDue ? "Show fewer" : `Show all ${due.length}`}
                </button>
              )}
            </>
          )}
        </Panel>
      </div>

      <Panel title="Portfolio by RM / Ops" right={<span className="text-xs text-gray-400">Click a name to see their companies</span>}>
        {people.length === 0 ? <EmptyState text="No RM or Ops users yet." /> : (
          <ul className="divide-y divide-gray-50">
            {people.map((r) => (
              <li key={r.user_id}>
                <button onClick={() => setOpen((p) => ({ ...p, [r.user_id]: !p[r.user_id] }))}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left">
                  <Icon name="chevronRight" size={14} className={`text-gray-400 transition-transform ${open[r.user_id] ? "rotate-90" : ""}`} />
                  <span className="w-40 min-w-0 truncate text-sm font-medium text-gray-800">{r.name}</span>
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 bg-gray-100 rounded px-1.5 py-0.5">{r.role}</span>
                  <span className="flex-1 hidden sm:block">
                    <span className="block h-1.5 rounded-full bg-gray-100 overflow-hidden">
                      <span className="block h-full rounded-full bg-brand-500" style={{ width: `${(r.total_cases / maxCases) * 100}%` }} />
                    </span>
                  </span>
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    <span className="font-semibold text-gray-800">{r.total_cases}</span> compan{r.total_cases === 1 ? "y" : "ies"} · {r.active_cases} onboarding
                  </span>
                </button>
                {open[r.user_id] && (
                  <div className="bg-gray-50/60 divide-y divide-gray-100">
                    {r.cases.length === 0 && <p className="text-xs text-gray-400 px-11 py-3">No companies assigned yet.</p>}
                    {r.cases.map((c) => (
                      <button key={c.case_id} onClick={() => onNavigate({ page: "cases", caseId: c.case_id })}
                        className="w-full flex items-center justify-between gap-2 pl-11 pr-4 py-2 hover:bg-white text-left">
                        <span className="min-w-0">
                          <span className="block text-xs font-medium text-gray-800 truncate">{c.company_name}</span>
                          <span className="block text-[11px] text-gray-400">{c.case_uid}</span>
                        </span>
                        <span className="flex gap-1.5 flex-shrink-0">
                          <Badge text={c.stage} />
                          <Badge text={c.invoice_status} />
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
