import React, { useEffect, useState } from "react";
import { useAuthStore } from "./store/auth";
import { Icon, ToastHost, ConfirmDialogHost } from "./components/ui";
import NotificationBell from "./components/NotificationBell";
import CommandPalette from "./components/CommandPalette";
import PageErrorBoundary from "./components/PageErrorBoundary";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import ProspectsPage from "./pages/ProspectsPage";
import AccountsPage from "./pages/AccountsPage";
import ActivitiesPage from "./pages/ActivitiesPage";
import InstructionsPage from "./pages/InstructionsPage";
import InvoicesPage from "./pages/InvoicesPage";
import ReportsPage from "./pages/ReportsPage";
import AdminPage from "./pages/AdminPage";
import ApprovalsPage from "./pages/ApprovalsPage";
import ChangePasswordModal from "./components/ChangePasswordModal";
import { ROLE_LABEL, fmtToday } from "./utils/constants";
import { formatTimestamp } from "./utils/auditFormat";

// The menu, grouped by area of work and ordered as the BRD flow runs: Prospect → Client → Compliance →
// servicing → invoicing. `desks`: client-facing staff (RM, RO, FO, Sales Manager) and Admin always see
// the item; central-desk users (Compliance, Approver, Accounts, Inquiry, Prospecting Coordinator) see it
// only with one of these permissions. No `desks` = everyone.
const NAV = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard", component: Dashboard, group: null },
  // Names and grouping per Triam's input of 19-10-2026.
  { key: "prospects", label: "Prospects", icon: "kanban", component: ProspectsPage, desks: ["prospect.assign", "client.approve", "read_only"], group: "Onboarding" },
  // Clients follow BRD §13 visibility: client-facing staff see their own; central desks only with a
  // "see clients" permission (Compliance, Approver, Accounts and Inquiry have one; the Prospecting
  // Coordinator doesn't, unless an administrator adds it to the role).
  { key: "accounts", label: "New Client Onboarding", icon: "accounts", component: AccountsPage, props: { scope: "onboarding" }, desks: ["view.all_clients", "view.department_clients"], group: "Onboarding" },
  // New clients and client amendments awaiting Compliance (MLRO) and Approver decisions (BRD §7–§11).
  { key: "approvals", label: "Compliance Approval", icon: "shield", component: ApprovalsPage, perm: ["client.approve", "client.final_approve"], group: "Compliance" },
  // Existing clients (BRD §11): amendments, servicing.
  { key: "maintenance", label: "Client Data Maintenance", icon: "edit", component: AccountsPage, props: { scope: "maintenance" }, desks: ["view.all_clients", "view.department_clients"], group: "Client Servicing" },
  { key: "activities", label: "Call Reports / Contact Notes", icon: "activities", component: ActivitiesPage, desks: ["view.all_clients", "view.department_clients"], group: "Client Servicing" },
  { key: "instructions", label: "Service Requests", icon: "instructions", component: InstructionsPage, desks: ["client.approve", "invoice.manage", "read_only"], group: "Client Servicing" },
  { key: "invoices", label: "Invoices", icon: "invoices", component: InvoicesPage, desks: ["client.approve", "invoice.manage", "read_only"], group: "Finance & Reports" },
  { key: "reports", label: "Reports", icon: "reports", component: ReportsPage, group: "Finance & Reports" },
  { key: "admin", label: "Admin", icon: "admin", component: AdminPage, roles: ["admin"], group: "Administration" },
];

export default function App() {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => !!s.accessToken);
  const logout = useAuthStore((s) => s.logout);
  // Hooks must all run before the early "not logged in" return below (React rules of hooks).
  const can = useAuthStore((s) => s.can);
  const [page, setPage] = useState("dashboard");
  // On a phone the menu starts closed and opens over the page; on a computer it is open beside the page.
  const isPhone = typeof window !== "undefined" && window.matchMedia("(max-width: 767px)").matches;
  const [sidebarOpen, setSidebarOpen] = useState(!isPhone);
  const [switchMenu, setSwitchMenu] = useState(false);
  const [jumpTo, setJumpTo] = useState(null);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const passwordWarning = useAuthStore((s) => s.passwordChangeRecommended);
  const clearPasswordWarning = useAuthStore((s) => s.clearPasswordWarning);
  // Each tab is one login: its title names the role, so a person working in several tabs can tell them apart.
  const roleLabel = user ? (user.business_role_name || ROLE_LABEL[user.role] || user.role) : null;
  useEffect(() => { document.title = roleLabel ? `TRIAM · ${roleLabel}` : "TRIAM CRM"; }, [roleLabel]);
  // Another of the person's logins opens in its own tab, on the sign-in page for that login.
  const openLogin = (l) => {
    const url = `${window.location.origin}/?as=${encodeURIComponent(l.email)}&role=${encodeURIComponent(l.role_name || "")}`;
    window.open(url, "_blank", "noopener");
  };

  if (!isAuthenticated) return <LoginPage />;

  const fullMenu = user?.role !== "rm" || user?.handles_clients !== false;
  const navItems = NAV.filter((n) => (!n.roles || n.roles.includes(user?.role)) && (!n.perm || [].concat(n.perm).some((f) => can(f)))
    && (!n.desks || fullMenu || n.desks.some((f) => can(f))));
  const activeItem = navItems.find((n) => n.key === page) || navItems[0];
  const PageComponent = activeItem.component;

  // Letters only: "Ritu (MLRO)" → "RM", not "R(".
  const avatar = (user?.name || "").replace(/[^A-Za-z\s]/g, " ").split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "?";
  const go = (key) => { setJumpTo(null); setPage(key); if (isPhone) setSidebarOpen(false); };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar — beside the page on a computer; over the page on a phone. */}
      {isPhone && sidebarOpen && <div className="fixed inset-0 z-30 bg-black/30" onClick={() => setSidebarOpen(false)} />}
      <aside className={`flex-shrink-0 flex flex-col border-r border-gray-100 bg-white transition-all duration-200 ${
        isPhone ? `fixed inset-y-0 left-0 z-40 w-64 shadow-xl ${sidebarOpen ? "" : "hidden"}` : sidebarOpen ? "w-60" : "w-16"}`}>
        {/* Brand: cropped wordmark when open, gold trident mark when collapsed. */}
        <div className={`flex items-center h-20 border-b border-gray-100 ${sidebarOpen ? "px-5" : "justify-center px-2"}`}>
          {sidebarOpen ? (
            <div>
              <img src="/triam-wordmark.png" alt="TRIAM" className="h-11 w-auto" />
            </div>
          ) : (
            <img src="/triam-trident.png" alt="TRIAM" className="h-10 w-auto" />
          )}
        </div>

        <nav className="flex-1 py-2 space-y-0.5 overflow-y-auto px-2">
          {navItems.map((item, i) => (
            <React.Fragment key={item.key}>
            {item.group && item.group !== navItems[i - 1]?.group && (sidebarOpen
              ? <div className="px-3 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">{item.group}</div>
              : <div className="mx-3 my-2 border-t border-gray-100" />)}
            <button onClick={() => go(item.key)}
              title={sidebarOpen ? undefined : item.label}
              className={`w-full flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm transition-colors text-left ${sidebarOpen ? "" : "justify-center"} ${page === item.key ? "text-white" : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"}`}
              style={page === item.key ? { background: "#1a3a5c" } : {}}>
              <Icon name={item.icon} size={18} className={`flex-shrink-0 ${page === item.key ? "text-gold" : ""}`} />
              {sidebarOpen && <span className="flex-1 font-medium">{item.label}</span>}
            </button>
            </React.Fragment>
          ))}
        </nav>

        <div className={`border-t border-gray-100 p-2 ${sidebarOpen ? "flex gap-1" : "space-y-1"}`}>
          <button onClick={() => setPasswordOpen(true)} title="Change password"
            className="flex-1 flex items-center justify-center gap-2 px-2 py-2 rounded-lg text-xs text-gray-500 hover:bg-gray-50 hover:text-gray-800">
            <Icon name="key" size={15} />{sidebarOpen && "Password"}
          </button>
          <button onClick={logout} title="Sign out"
            className="flex-1 flex items-center justify-center gap-2 px-2 py-2 rounded-lg text-xs text-gray-500 hover:bg-red-50 hover:text-red-600">
            <Icon name="logout" size={15} />{sidebarOpen && "Sign out"}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {passwordWarning && (
          // the account still uses a default password.
          <div className="flex flex-wrap items-center gap-3 px-6 py-2 bg-amber-50 border-b border-amber-200 text-sm text-amber-900">
            <span className="flex-1">You signed in with a default password. Please change it now to keep client data safe.</span>
            <button onClick={() => setPasswordOpen(true)} className="px-3 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Change password</button>
          </div>
        )}
        {passwordOpen && (
          <ChangePasswordModal onClose={() => setPasswordOpen(false)} onChanged={clearPasswordWarning}
            reason={passwordWarning ? "This account still uses a default password." : null} />
        )}
        <header className="flex items-center justify-between gap-2 px-3 md:px-6 py-3 bg-white border-b border-gray-100">
          <button onClick={() => setSidebarOpen((o) => !o)} className="text-gray-400 hover:text-gray-600 p-1 rounded">
            <Icon name="menu" size={20} />
          </button>
          <div className="flex items-center gap-2 md:gap-3 min-w-0">
            <CommandPalette onNavigate={(t) => { setJumpTo(t); setPage(t.page); }} />
            <div className="text-xs text-gray-500 bg-gray-100 px-3 py-1.5 rounded-lg hidden sm:block">
              {fmtToday()}
            </div>
            <NotificationBell />
            {user && (
              <div className="flex items-center gap-2.5 pl-3 border-l border-gray-100"
                title={[user.last_login_at && `Logged in ${formatTimestamp(user.last_login_at)}`, user.previous_login_at && `Last login ${formatTimestamp(user.previous_login_at)}`].filter(Boolean).join("\n")}>
                <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center" style={{ background: "#1a3a5c" }}>{avatar}</div>
                <div className="hidden md:block leading-tight">
                  <div className="text-sm font-semibold text-gray-800">{user.name}</div>
                  <div className="text-[11px] text-gray-500">
                    <span className="font-semibold text-brand-700">{roleLabel}</span>
                    {(user.linked_logins || []).length > 0 && (
                      <span className="relative ml-1.5">
                        <button type="button" onClick={() => setSwitchMenu((o) => !o)} title="Switch to another of your logins"
                          className="px-1.5 py-0 text-[11px] text-brand-700 border border-gray-200 rounded hover:border-brand-300">Switch ▾</button>
                        {switchMenu && (
                          <span className="absolute right-0 top-5 z-40 w-64 py-1 bg-white border border-gray-200 rounded-lg shadow-lg">
                            {user.linked_logins.map((l) => (
                              <button key={l.id} type="button" onClick={() => { setSwitchMenu(false); openLogin(l); }}
                                className="block w-full text-left px-3 py-1.5 hover:bg-gray-50">
                                <span className="flex items-center justify-between text-xs font-medium text-gray-800">
                                  {l.role_name || "Login"}<span className="text-[10px] font-normal text-brand-600">Open in new tab ↗</span>
                                </span>
                                <span className="block text-[11px] text-gray-500 truncate">{l.email}</span>
                              </button>
                            ))}
                          </span>
                        )}
                      </span>
                    )}
                    {(user.permissions || []).includes("read_only") && <span className="ml-1 px-1 rounded bg-gray-100 text-gray-500">Read-only</span>}
                  </div>
                  {user.last_login_at && <div className="text-[10px] text-gray-400">Logged in {formatTimestamp(user.last_login_at)}</div>}
                </div>
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-3 md:p-6">
          <PageErrorBoundary key={`${page}-${user?.id}`}>
          <PageComponent
            {...(activeItem.props || {})}
            onNavigate={(t) => { setJumpTo(t); setPage(t.page); }}
            initialAccountId={jumpTo?.page === activeItem.key ? jumpTo.accountId : undefined}
            initialOpenForm={jumpTo?.page === activeItem.key ? !!jumpTo.openForm : undefined}
            initialProspectId={jumpTo?.page === "accounts" ? jumpTo.prospectId : undefined}
          />
          </PageErrorBoundary>
        </main>
      </div>

      <ToastHost />
      <ConfirmDialogHost />
    </div>
  );
}
