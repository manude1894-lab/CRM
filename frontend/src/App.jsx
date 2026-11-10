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
import IdleSignOut from "./components/IdleSignOut";
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
  { key: "approvals", label: "Compliance Approval", icon: "shield", component: ApprovalsPage, perm: ["client.approve", "client.final_approve", "read_only"], group: "Compliance" },
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
  // On a computer the sidebar folds to an icon rail and remembers the choice (per browser).
  const [sidebarOpen, setSidebarOpenState] = useState(() => {
    if (isPhone) return false;
    try { return localStorage.getItem("triam-sidebar") !== "collapsed"; } catch { return true; }
  });
  const setSidebarOpen = (next) => setSidebarOpenState((prev) => {
    const value = typeof next === "function" ? next(prev) : next;
    if (!isPhone) { try { localStorage.setItem("triam-sidebar", value ? "open" : "collapsed"); } catch { /* storage unavailable */ } }
    return value;
  });
  const [profileMenu, setProfileMenu] = useState(false);
  // Ctrl+B (Cmd+B on a Mac) folds or unfolds the sidebar, as in most modern tools.
  useEffect(() => {
    if (isPhone) return undefined;
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "b"
          && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "") && !document.activeElement?.isContentEditable) {
        e.preventDefault();
        setSidebarOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isPhone]); // eslint-disable-line react-hooks/exhaustive-deps
  const [touchX, setTouchX] = useState(null);
  useEffect(() => {
    if (!profileMenu) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setProfileMenu(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [profileMenu]);
  const [jumpTo, setJumpTo] = useState(null);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const passwordWarning = useAuthStore((s) => s.passwordChangeRecommended);
  const clearPasswordWarning = useAuthStore((s) => s.clearPasswordWarning);
  // Each tab is one login: its title names the role, so a person working in several tabs can tell them apart.
  const roleLabel = user ? (user.business_role_name || ROLE_LABEL[user.role] || user.role) : null;
  useEffect(() => { document.title = roleLabel ? `TRIAM · ${roleLabel}` : "TRIAM CRM"; }, [roleLabel]);
  // Another of the person's logins opens in its own tab, on the sign-in page with that email filled in.
  const openLogin = (l) => {
    try { localStorage.setItem("triam-switch", JSON.stringify({ email: l.email, at: Date.now() })); } catch { /* storage unavailable */ }
    window.open(`${window.location.origin}/`, "_blank", "noopener");
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
      <aside
        // On a phone, swiping the menu to the left closes it.
        onTouchStart={isPhone ? (e) => setTouchX(e.touches[0].clientX) : undefined}
        onTouchEnd={isPhone ? (e) => { if (touchX !== null && e.changedTouches[0].clientX - touchX < -60) setSidebarOpen(false); setTouchX(null); } : undefined}
        className={`relative flex-shrink-0 flex flex-col border-r border-gray-100 bg-white transition-all duration-200 ${
        isPhone ? `fixed inset-y-0 left-0 z-40 w-64 shadow-xl ${sidebarOpen ? "" : "hidden"}` : sidebarOpen ? "w-60" : "w-16"}`}>
        {/* Brand: cropped wordmark when open, gold trident mark when collapsed. */}
        <div className={`flex items-center h-20 border-b border-gray-100 ${sidebarOpen ? "px-5" : "justify-center px-2"}`}>
          {sidebarOpen ? (
            <img src="/triam-wordmark.png" alt="TRIAM" className="h-11 w-auto" />
          ) : (
            <img src="/triam-trident.png" alt="TRIAM" className="h-10 w-auto" />
          )}
        </div>
        {/* Collapse handle on the sidebar's edge (Ctrl+B also toggles); on a phone the menu closes by swipe or backdrop. */}
        {!isPhone && (
          <button onClick={() => setSidebarOpen((o) => !o)} title={`${sidebarOpen ? "Collapse" : "Expand"} menu (Ctrl+B)`}
            aria-label={sidebarOpen ? "Collapse menu" : "Expand menu"}
            className="absolute -right-3 top-[68px] z-30 w-6 h-6 rounded-full bg-white border border-gray-200 shadow-sm flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#1a3a5c] hover:border-[#1a3a5c] transition-colors">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round">
              <path d={sidebarOpen ? "M15 18l-6-6 6-6" : "M9 18l6-6-6-6"} />
            </svg>
          </button>
        )}

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
          {/* On a phone the menu is hidden until opened from here; on a computer the toggle is in the sidebar. */}
          {isPhone ? (
            <button onClick={() => setSidebarOpen(true)} title="Open menu" aria-label="Open menu"
              className="p-1 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100">
              {/* Fine-line "side panel" icon */}
              <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="16" rx="2.5" /><path d="M9 4v16" />
              </svg>
            </button>
          ) : <span />}
          <div className="flex items-center gap-2 md:gap-3 min-w-0">
            <CommandPalette onNavigate={(t) => { setJumpTo(t); setPage(t.page); }} />
            <div className="text-xs text-gray-500 bg-gray-100 px-3 py-1.5 rounded-lg hidden sm:block">
              {fmtToday()}
            </div>
            <NotificationBell onNavigate={(t) => { setJumpTo({ ...t, nonce: Date.now() }); setPage(t.page); }} />
            {user && (
              <div className="relative pl-3 border-l border-gray-100">
                {/* Profile menu: who is signed in, switching login, password and sign out. */}
                <button type="button" onClick={() => setProfileMenu((o) => !o)} aria-haspopup="menu" aria-expanded={profileMenu}
                  title="Your profile" className="flex items-center gap-2.5 rounded-lg px-1.5 py-1 hover:bg-gray-50 text-left">
                  <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center" style={{ background: "#1a3a5c" }}>{avatar}</div>
                  <div className="hidden md:block leading-tight">
                    <div className="text-sm font-semibold text-gray-800">{user.name}</div>
                    <div className="text-[11px] text-gray-500">
                      <span className="font-semibold text-brand-700">{roleLabel}</span>
                      {(user.permissions || []).includes("read_only") && <span className="ml-1 px-1 rounded bg-gray-100 text-gray-500">Read-only</span>}
                    </div>
                  </div>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" className={`hidden md:block text-gray-400 transition-transform ${profileMenu ? "rotate-180" : ""}`}><path d="M7 10l5 5 5-5z" /></svg>
                </button>
                {profileMenu && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setProfileMenu(false)} />
                    <div role="menu" className="absolute right-0 top-12 z-50 w-72 bg-white border border-gray-200 rounded-xl shadow-lg overflow-hidden">
                      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
                        <div className="w-10 h-10 rounded-full text-white text-sm font-bold flex items-center justify-center flex-shrink-0" style={{ background: "#1a3a5c" }}>{avatar}</div>
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-gray-800 truncate">{user.name}</div>
                          <div className="text-xs text-gray-500 truncate">{user.email}</div>
                          <div className="text-[11px] font-semibold text-brand-700">{roleLabel}</div>
                        </div>
                      </div>
                      {(user.previous_login_at || user.last_login_at) && (
                        <div className="px-4 py-2 text-[11px] text-gray-400 border-b border-gray-100">
                          {user.previous_login_at ? `Last login ${formatTimestamp(user.previous_login_at)}` : `Logged in ${formatTimestamp(user.last_login_at)}`}
                        </div>
                      )}
                      {(user.linked_logins || []).length > 0 && (
                        <div className="py-1 border-b border-gray-100">
                          <div className="px-4 pt-1 pb-0.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400">Switch login</div>
                          {user.linked_logins.map((l) => (
                            <button key={l.id} type="button" role="menuitem" onClick={() => { setProfileMenu(false); openLogin(l); }}
                              className="block w-full text-left px-4 py-1.5 hover:bg-gray-50">
                              <span className="block text-xs font-medium text-gray-800">{l.role_name || "Login"}</span>
                              <span className="block text-[11px] text-gray-500 truncate">{l.email}</span>
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="py-1">
                        <button type="button" role="menuitem" onClick={() => { setProfileMenu(false); setPasswordOpen(true); }}
                          className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                          <Icon name="key" size={16} className="text-gray-400" /> Change password
                        </button>
                        <button type="button" role="menuitem" onClick={() => { setProfileMenu(false); logout(); }}
                          className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50">
                          <Icon name="logout" size={16} /> Sign out
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-3 md:p-6">
          <PageErrorBoundary key={`${page}-${user?.id}-${jumpTo?.nonce || ""}`}>
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
      <IdleSignOut />
    </div>
  );
}
