import { formatTimestamp } from "../utils/auditFormat";
import React, { useEffect, useState } from "react";
import { dashboardApi, accountsApi } from "../api/endpoints";
import { Icon, Spinner, ErrorBanner } from "../components/ui";
import { fmtDate } from "../utils/constants";
import { useAuthStore } from "../store/auth";

const DUE_SOON_DAYS = 60;
const REFRESH_MS = 5 * 60 * 1000;

// Client dates surfaced in "Due soon" (BRD §5, §8, §9, §20).
const ACCOUNT_DUE_FIELDS = [
  ["license_expiry_date", "Trade licence expiry"],
  ["next_aml_review_date", "AML review"],
  ["engagement_letter_valid_until", "Engagement letter"],
  ["lei_expiry_date", "LEI expiry"],
  ["uae_visa_expiry", "UAE visa expiry"],
  ["passport_expiry_date", "Passport expiry"],
];
const SERVICED = ["Approved", "Active", "Inactive", "Marked for Exit"];

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

/** BRD §9 — the client lifecycle New → … → Exited, with how many clients are at each status. */
function Lifecycle({ statuses, onOpen }) {
  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-[720px]">
        {statuses.map((s, i) => {
          const busy = s.count > 0;
          return (
            <button key={s.status} onClick={onOpen} title={`${s.status}: ${s.count}`}
              className="flex-1 min-w-0 relative group px-1 pt-3 pb-3 flex flex-col items-center justify-start text-center">
              <span className={`absolute top-[26px] h-0.5 bg-gray-200 ${i === 0 ? "left-1/2 right-0" : i === statuses.length - 1 ? "left-0 right-1/2" : "left-0 right-0"}`} />
              <span className={`relative mx-auto flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold tabular-nums transition-colors
                ${busy ? "bg-brand-600 text-white ring-4 ring-brand-50" : "bg-white text-gray-400 border border-gray-200 group-hover:border-brand-300"}`}>
                {s.count}
              </span>
              <span className={`block mt-2 text-[11px] leading-tight ${busy ? "text-gray-800 font-medium" : "text-gray-400"}`}>{s.status}</span>
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
  const [showAllDue, setShowAllDue] = useState(false);
  const [myWork, setMyWork] = useState([]);

  const load = async () => {
    try {
      setError(null);
      const [dash, accs, work] = await Promise.all([dashboardApi.get(), accountsApi.list({ limit: 200 }).catch(() => []),
        dashboardApi.myWork().catch(() => [])]);
      setData(dash);
      setMyWork(work || []);
      setAccounts(Array.isArray(accs?.items) ? accs.items : []);
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
  const goClient = (id) => onNavigate({ page: "accounts", accountId: id });

  // Due soon: dates on the clients Triam services, overdue first.
  const due = accounts.filter((a) => SERVICED.includes(a.profile_status)).flatMap((a) => ACCOUNT_DUE_FIELDS
    .filter(([f]) => a[f] && daysUntil(a[f]) <= DUE_SOON_DAYS)
    .map(([f, what]) => ({ key: `${a.id}-${f}`, id: a.id, company: a.company_name, what, date: a[f], days: daysUntil(a[f]) })))
    .sort((x, y) => x.days - y.days);
  const dueShown = showAllDue ? due : due.slice(0, 8);

  const people = data.portfolio_by_rm || [];
  const maxClients = Math.max(1, ...people.map((p) => p.total));

  return (
    <div className="max-w-[1400px] mx-auto space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{greeting()}{user?.name ? `, ${user.name.split(" ")[0]}` : ""}</h1>
          {user?.previous_login_at && <p className="text-xs text-gray-400 mt-0.5">Last login {formatTimestamp(user.previous_login_at)}</p>}
        </div>
        <button onClick={load} className="text-xs text-gray-400 hover:text-brand-600">
          Updated {updatedAt?.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · Refresh
        </button>
      </div>

      {/* BRD §2 — role-level dashboard: the work waiting for this user. */}
      {myWork.some((w) => w.count > 0) && (
        <Panel title="My work" right={<span className="text-xs text-gray-400">{user?.business_role_name || ""}</span>}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 p-3">
            {myWork.filter((w) => w.count > 0).map((w) => (
              <button key={w.key} onClick={() => onNavigate({ page: w.page })}
                className="flex items-center gap-3 text-left rounded-lg border border-gray-100 hover:border-brand-300 hover:bg-brand-50/40 px-3 py-2.5">
                <span className="text-2xl font-bold text-brand-700 w-10 text-center">{w.count}</span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-gray-800">{w.label}</span>
                  {w.hint && <span className="block text-[11px] text-gray-400">{w.hint}</span>}
                </span>
              </button>
            ))}
          </div>
        </Panel>
      )}

      {/* BRD §2 — snapshot MI. */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Open prospects" value={kpis.prospects_open} icon="kanban" onClick={() => onNavigate({ page: "prospects" })} />
        <StatCard label="Prospects to assign" value={kpis.prospects_unassigned} attention hint="Assign an RM" icon="warn" onClick={() => onNavigate({ page: "prospects" })} />
        <StatCard label="Clients being prepared" value={kpis.clients_in_progress} icon="accounts" onClick={() => onNavigate({ page: "accounts" })} />
        <StatCard label="Awaiting approval" value={kpis.clients_awaiting_approval} attention hint="With Compliance / Approver" icon="shield" onClick={() => onNavigate({ page: "approvals" })} />
        <StatCard label="Approved & active clients" value={kpis.clients_active} icon="check" onClick={() => onNavigate({ page: "maintenance" })} />
        <StatCard label="Open service requests" value={kpis.service_requests_open} icon="instructions" onClick={() => onNavigate({ page: "instructions" })} />
        <StatCard label="Unpaid invoices" value={kpis.invoices_unpaid} attention hint="Follow up payment" icon="invoices" onClick={() => onNavigate({ page: "invoices" })} />
        <StatCard label={`AML reviews due (${DUE_SOON_DAYS} days)`} value={kpis.aml_reviews_due} attention hint="Plan the reviews" icon="calendar" onClick={() => onNavigate({ page: "reports" })} />
      </div>

      <Panel title="Client lifecycle"
        right={<span className="text-xs text-gray-400">With Compliance {data.approvals_pending.compliance} · With the Approver {data.approvals_pending.approver}</span>}>
        <div className="px-3 py-2">
          <Lifecycle statuses={data.client_status_breakdown || []} onOpen={() => onNavigate({ page: "accounts" })} />
        </div>
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel title={`Due soon (next ${DUE_SOON_DAYS} days)`} right={due.length > 0 && <span className="text-xs font-medium text-gray-500">{due.length}</span>}>
          {due.length === 0 ? <EmptyState text={`Nothing due in the next ${DUE_SOON_DAYS} days.`} /> : (
            <>
              <ul className="divide-y divide-gray-50">
                {dueShown.map((d) => (
                  <li key={d.key}>
                    <button onClick={() => goClient(d.id)} className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left">
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

        <Panel title="Portfolio by RM">
          {people.length === 0 ? <EmptyState text="No relationship managers with clients yet." /> : (
            <ul className="divide-y divide-gray-50">
              {people.map((r) => (
                <li key={r.user_id} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="w-40 min-w-0 truncate text-sm font-medium text-gray-800">{r.name}</span>
                  <span className="flex-1 hidden sm:block">
                    <span className="block h-1.5 rounded-full bg-gray-100 overflow-hidden">
                      <span className="block h-full rounded-full bg-brand-500" style={{ width: `${(r.total / maxClients) * 100}%` }} />
                    </span>
                  </span>
                  <span className="text-xs text-gray-500 whitespace-nowrap">
                    <span className="font-semibold text-gray-800">{r.total}</span> client{r.total === 1 ? "" : "s"} · {r.in_progress} onboarding · {r.active} active
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
