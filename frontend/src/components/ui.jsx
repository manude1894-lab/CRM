import React from "react";
import { ROLE_LABEL } from "../utils/constants";

// ─── Icon ───────────────────────────────────────────────────────────────
export const Icon = ({ name, size = 18, className = "" }) => {
  const icons = {
    dashboard: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z",
    cases: "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z",
    cdd: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
    compliance: "M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm2 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z",
    accounts: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
    activities: "M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2zm.5 5v5.25l4.5 2.67-.75 1.23L11 13V7h1.5z",
    reports: "M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-4 14H7v-2h8v2zm2-4H7v-2h10v2zm0-4H7V7h10v2z",
    admin: "M17 12h-5v5h5v-5zM16 1v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2h-1V1h-2zm3 18H5V8h14v11z",
    logout: "M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z",
    search: "M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
    plus: "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    edit: "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
    del: "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
    close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
    sort: "M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z",
    check: "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
    warn: "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    kanban: "M2 4c0-1.1.9-2 2-2h4c1.1 0 2 .9 2 2v16c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V4zm7 0c0-1.1.9-2 2-2h4c1.1 0 2 .9 2 2v10c0 1.1-.9 2-2 2h-4c-1.1 0-2-.9-2-2V4zm9 0c0-1.1.9-2 2-2h2c1.1 0 2 .9 2 2v6c0 1.1-.9 2-2 2h-2c-1.1 0-2-.9-2-2V4z",
    table: "M20 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h15c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3h5v2h-5V6zm0 4h5v2h-5v-2zM8 6h4v2H8V6zm0 4h4v2H8v-2zm-3 0h2v2H5v-2zM5 6h2v2H5V6zm0 8h14v2H5v-2z",
    menu: "M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z",
    download: "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
    bell: "M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z",
    instructions: "M19 3h-4.18C14.4 1.84 13.3 1 12 1c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1zM7 12h2v5H7v-5zm4-3h2v8h-2V9zm4 5h2v3h-2v-3z",
    invoices: "M6 2h12a1 1 0 0 1 1 1v18l-3-2-3 2-3-2-3 2-3-2V3a1 1 0 0 1 1-1zm2 5h8V5H8v2zm0 4h8V9H8v2zm0 4h5v-2H8v2z",
  };
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" className={className}>
      <path d={icons[name] || ""} />
    </svg>
  );
};

// ─── Badge ──────────────────────────────────────────────────────────────
export const Badge = ({ text }) => {
  const label = ROLE_LABEL[text] || text;
  const styles = {
    // Case stages
    "New Inquiry": "bg-gray-100 text-gray-600",
    "RM Assigned": "bg-sky-100 text-sky-700",
    "Docs Requested": "bg-blue-100 text-blue-700",
    "CDD/KYC In Review": "bg-indigo-100 text-indigo-700",
    "CDD Approved": "bg-purple-100 text-purple-700",
    "Invoice Raised": "bg-orange-100 text-orange-700",
    "Invoice Paid": "bg-amber-100 text-amber-700",
    "Ops Assigned": "bg-teal-100 text-teal-700",
    "Application Submitted": "bg-lime-100 text-lime-700",
    "License Received": "bg-emerald-100 text-emerald-700",
    Active: "bg-emerald-100 text-emerald-700",
    // Case status overlay
    "Docs Pending": "bg-amber-100 text-amber-700",
    Rejected: "bg-red-100 text-red-700",
    "On Hold": "bg-gray-100 text-gray-600",
    // Document / CDD statuses
    "Not Started": "bg-gray-100 text-gray-600",
    Submitted: "bg-blue-100 text-blue-700",
    "Under Review": "bg-indigo-100 text-indigo-700",
    Approved: "bg-emerald-100 text-emerald-700",
    // Invoice statuses
    "Not Raised": "bg-gray-100 text-gray-600",
    Raised: "bg-orange-100 text-orange-700",
    Paid: "bg-emerald-100 text-emerald-700",
    // Generic risk-style badges (kept for reuse)
    High: "bg-red-100 text-red-700",
    Medium: "bg-amber-100 text-amber-700",
    Low: "bg-green-100 text-green-700",
    // Roles
    Admin: "bg-red-100 text-red-700",
    "Relationship Manager": "bg-blue-100 text-blue-700",
    Ops: "bg-teal-100 text-teal-700",
    Screening: "bg-purple-100 text-purple-700",
    // Activity types
    Meeting: "bg-blue-100 text-blue-700",
    Demo: "bg-purple-100 text-purple-700",
    Call: "bg-green-100 text-green-700",
    Email: "bg-gray-100 text-gray-600",
    "Follow-up": "bg-amber-100 text-amber-700",
    // Instruction statuses
    Pending: "bg-amber-100 text-amber-700",
    "In Progress": "bg-blue-100 text-blue-700",
    Completed: "bg-emerald-100 text-emerald-700",
    // Invoice ledger statuses
    Draft: "bg-gray-100 text-gray-600",
    Overdue: "bg-red-100 text-red-700",
  };
  const cls = styles[text] || styles[label] || "bg-gray-100 text-gray-600";
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>;
};

// ─── MetricCard ─────────────────────────────────────────────────────────
export const MetricCard = ({ label, value, sub, color = "#2B6D9A", icon }) => (
  <div className="bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold mt-1" style={{ color }}>{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
      </div>
      {icon && (
        <div className="p-2 rounded-lg" style={{ background: color + "15", color }}>
          <Icon name={icon} size={22} />
        </div>
      )}
    </div>
  </div>
);

// ─── Modal ──────────────────────────────────────────────────────────────
export const Modal = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.4)" }}>
    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-800">{title}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
          <Icon name="close" size={20} />
        </button>
      </div>
      <div className="p-6">{children}</div>
    </div>
  </div>
);

// ─── Form primitives ────────────────────────────────────────────────────
export const Field = ({ label, children, required }) => (
  <div className="mb-4">
    <label className="block text-xs font-medium text-gray-600 mb-1">
      {label}{required && <span className="text-red-400 ml-0.5">*</span>}
    </label>
    {children}
  </div>
);

export const Input = (props) => (
  <input
    {...props}
    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100"
  />
);

export const Select = ({ children, ...props }) => (
  <select
    {...props}
    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
  >
    {children}
  </select>
);

export const Textarea = (props) => (
  <textarea
    {...props}
    rows={3}
    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400 resize-none"
  />
);

// ─── Chart Tooltip ──────────────────────────────────────────────────────
export const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-1">{label}</p>
      {payload.map((p, i) => {
        const v = typeof p.value === "number" && p.value > 999 ? `$${(p.value / 1e6).toFixed(2)}M` : p.value;
        return (
          <p key={i} style={{ color: p.color }}>
            {p.name}: {v}
          </p>
        );
      })}
    </div>
  );
};

// ─── Loading spinner ────────────────────────────────────────────────────
export const Spinner = ({ size = 40 }) => (
  <div className="flex items-center justify-center p-8">
    <div
      className="animate-spin rounded-full border-4 border-gray-200"
      style={{ width: size, height: size, borderTopColor: "#2B6D9A" }}
    />
  </div>
);

// ─── Error banner ───────────────────────────────────────────────────────
export const ErrorBanner = ({ message, onRetry }) => (
  <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 flex items-center justify-between">
    <div className="flex items-center gap-2">
      <Icon name="warn" size={18} />
      <span className="text-sm">{message}</span>
    </div>
    {onRetry && (
      <button onClick={onRetry} className="text-sm font-medium underline">
        Retry
      </button>
    )}
  </div>
);
