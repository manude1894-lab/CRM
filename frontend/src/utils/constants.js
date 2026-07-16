// Case stage pipeline (11 stages) — mirrors backend CaseStage
export const STAGES = [
  "New Inquiry",
  "RM Assigned",
  "Docs Requested",
  "CDD/KYC In Review",
  "CDD Approved",
  "Invoice Raised",
  "Invoice Paid",
  "Ops Assigned",
  "Application Submitted",
  "License Received",
  "Active",
];

export const STAGE_COLORS = {
  "New Inquiry": "#94a3b8",
  "RM Assigned": "#60a5fa",
  "Docs Requested": "#38bdf8",
  "CDD/KYC In Review": "#a78bfa",
  "CDD Approved": "#8b5cf6",
  "Invoice Raised": "#fb923c",
  "Invoice Paid": "#f59e0b",
  "Ops Assigned": "#34d399",
  "Application Submitted": "#22c55e",
  "License Received": "#10b981",
  "Active": "#2B6D9A",
};

export const CASE_STATUS_COLORS = {
  "Active": "bg-green-100 text-green-700",
  "Docs Pending": "bg-amber-100 text-amber-700",
  "Rejected": "bg-red-100 text-red-700",
  "On Hold": "bg-gray-100 text-gray-600",
};

export const DOCUMENT_STATUS_OPTIONS = ["Not Started", "Submitted", "Under Review", "Approved", "Rejected"];

export const CASE_SOURCE_OPTIONS = ["Senior Mgmt", "Social Media", "Referral", "Other"];

export const PIE_COLORS = [
  "#2B6D9A", "#34d399", "#fb923c", "#a78bfa",
  "#60a5fa", "#f59e0b", "#ef4444", "#ec4899",
];

export const fmt = (n) => {
  const v = Number(n || 0);
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
};

export const fmtFull = (n) => `$${Number(n || 0).toLocaleString()}`;

export const ROLE_LABEL = {
  admin: "Admin",
  rm: "Relationship Manager",
  ops: "Ops",
  screening: "Screening",
};
