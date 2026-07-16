import React, { useState } from "react";
import { useAuthStore } from "./store/auth";
import { Icon, Badge } from "./components/ui";
import NotificationBell from "./components/NotificationBell";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import CasesPage from "./pages/CasesPage";
import CDDPage from "./pages/CDDPage";
import CompliancePage from "./pages/CompliancePage";
import AccountsPage from "./pages/AccountsPage";
import ActivitiesPage from "./pages/ActivitiesPage";
import ReportsPage from "./pages/ReportsPage";
import AdminPage from "./pages/AdminPage";
import { ROLE_LABEL } from "./utils/constants";

const NAV = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard", component: Dashboard },
  { key: "cases", label: "Cases", icon: "cases", component: CasesPage },
  { key: "cdd", label: "CDD / Screening", icon: "cdd", component: CDDPage, roles: ["admin", "screening"] },
  { key: "compliance", label: "Compliance", icon: "compliance", component: CompliancePage },
  { key: "accounts", label: "Accounts", icon: "accounts", component: AccountsPage },
  { key: "activities", label: "Activities", icon: "activities", component: ActivitiesPage },
  { key: "reports", label: "Reports", icon: "reports", component: ReportsPage },
  { key: "admin", label: "Admin", icon: "admin", component: AdminPage, roles: ["admin"] },
];

export default function App() {
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => !!s.accessToken);
  const logout = useAuthStore((s) => s.logout);
  const [page, setPage] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  if (!isAuthenticated) return <LoginPage />;

  const navItems = NAV.filter((n) => !n.roles || n.roles.includes(user?.role));
  const activeItem = navItems.find((n) => n.key === page) || navItems[0];
  const PageComponent = activeItem.component;

  const avatar = user?.name?.split(" ").map((n) => n[0]).slice(0, 2).join("") || "?";

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className={`flex-shrink-0 flex flex-col border-r border-gray-100 bg-white transition-all duration-200 ${sidebarOpen ? "w-56" : "w-16"}`}>
        <div className="flex items-center gap-3 px-4 py-5 border-b border-gray-100">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: "#2B6D9A" }}>
            <span className="text-white font-bold text-sm">E</span>
          </div>
          {sidebarOpen && (
            <div>
              <div className="text-sm font-bold text-gray-800">EZEETECH GROUP</div>
              <div className="text-xs text-gray-400">CRM Platform</div>
            </div>
          )}
        </div>

        <nav className="flex-1 py-3 space-y-0.5 overflow-y-auto px-2">
          {navItems.map((item) => (
            <button key={item.key} onClick={() => setPage(item.key)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-colors text-left ${page === item.key ? "text-white" : "text-gray-600 hover:bg-gray-50 hover:text-gray-800"}`}
              style={page === item.key ? { background: "#2B6D9A" } : {}}>
              <Icon name={item.icon} size={18} className="flex-shrink-0" />
              {sidebarOpen && <span className="flex-1 font-medium">{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="border-t border-gray-100 p-3">
          <div className={`flex items-center gap-3 ${sidebarOpen ? "" : "justify-center"}`}>
            <div className="w-8 h-8 rounded-full text-white text-xs font-bold flex items-center justify-center flex-shrink-0" style={{ background: "#2B6D9A" }}>
              {avatar}
            </div>
            {sidebarOpen && (
              <>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-gray-800 truncate">{user?.name}</div>
                  <div className="text-xs text-gray-400 truncate">{ROLE_LABEL[user?.role] || user?.role}</div>
                </div>
                <button onClick={logout} className="text-gray-400 hover:text-red-500" title="Logout">
                  <Icon name="logout" size={16} />
                </button>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-100">
          <button onClick={() => setSidebarOpen((o) => !o)} className="text-gray-400 hover:text-gray-600 p-1 rounded">
            <Icon name="menu" size={20} />
          </button>
          <div className="flex items-center gap-3">
            <div className="text-xs text-gray-500 bg-gray-100 px-3 py-1.5 rounded-lg hidden sm:block">
              {new Date().toLocaleDateString("en-US", { weekday: "short", year: "numeric", month: "short", day: "numeric" })}
            </div>
            <NotificationBell />
            {user && <Badge text={user.role} />}
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          <PageComponent />
        </main>
      </div>
    </div>
  );
}
