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
  "In Closure": "bg-amber-100 text-amber-700",
  "Struck Off": "bg-red-100 text-red-700",
  "Dissolved": "bg-gray-200 text-gray-700",
  "Transferred Out": "bg-gray-200 text-gray-700",
};

export const CASE_STATUS_OPTIONS = [
  "Active", "Docs Pending", "On Hold", "Rejected",
  "In Closure", "Struck Off", "Dissolved", "Transferred Out",
];

// The exited statuses — hidden from the default Cases view, shown as "Closed RELs".
export const CLOSED_REL_STATUSES = ["Struck Off", "Dissolved", "Transferred Out"];

export const CLOSURE_METHOD_OPTIONS = [
  "Voluntary Liquidation",
  "Voluntary Strike Off",
  "Lapse by Non-Payment",
];

export const RESTORATION_STATUS_OPTIONS = ["Not Applicable", "In Progress", "Completed"];

export const STRIKE_OFF_CAUSE_OPTIONS = ["Client-related", "Agent-related", "Other"];

export const LIFECYCLE_CHECKLIST_STATUS_OPTIONS = ["Pending", "Received", "N/A"];

// Process Manual §XI — restoration document checklist (keys match the backend template).
export const RESTORATION_CHECKLIST_ITEMS = [
  { key: "ci", label: "Certificate of Incorporation (CI)" },
  { key: "rom", label: "Register of Members (ROM)" },
  { key: "rod", label: "Register of Directors (ROD)" },
  { key: "rod_stamped", label: "Register of Directors — stamped (ROD Stamped)" },
  { key: "moa", label: "Memorandum & Articles of Association (M&A)" },
  { key: "resolution_carrying_business", label: "Resolution on carrying on business" },
  { key: "es_fy_start_confirmation", label: "ES financial year start-date confirmation" },
  { key: "es_filing_2020_2024", label: "2020–2024 Economic Substance filing status" },
  { key: "ar_2023_form", label: "2023 Annual Return submission form" },
  { key: "ar_2024_form", label: "2024 Annual Return submission form" },
  { key: "bo_form", label: "BO / ROM-RBO form" },
  { key: "indemnity_letter", label: "Indemnity letter" },
  { key: "resolution_appointing_vistra", label: "Resolution appointing Vistra / RORA" },
  { key: "bvi_record_keeping_resolution", label: "BVI record-keeping resolution" },
  { key: "rom_bvi_form", label: "ROM BVI form" },
];

export const DOCUMENT_STATUS_OPTIONS = ["Not Started", "Submitted", "Under Review", "Approved", "Rejected"];

export const CASE_SOURCE_OPTIONS = ["Senior Mgmt", "Social Media", "Referral", "Other"];

export const JURISDICTION_OPTIONS = [
  "BVI",
  "Cayman Islands",
  "Seychelles",
  "Jersey",
  "Guernsey",
  "Isle of Man",
  "Mauritius",
  "Other",
];

export const SERVICE_TYPE_OPTIONS = [
  "Company Formation",
  "ESR Filing",
  "Annual Return",
  "Ownership Update",
  "Document Provision",
  "CDD Submission",
  "Company Closure",
  "Restoration",
  "Other",
];

export const AML_RISK_OPTIONS = ["Low", "Medium", "High"];

export const PARTY_TYPE_OPTIONS = ["Individual", "Corporate"];

export const SHAREHOLDER_TYPE_OPTIONS = ["Individual", "BC Company", "Non-BVI Entity", "Limited Partnership"];

export const OWNERSHIP_NATURE_OPTIONS = ["Direct", "Indirect"];

export const SOURCE_OF_WEALTH_OPTIONS = [
  "Employment income / bonus",
  "Business owner / entrepreneur",
  "Inheritance / gift",
  "Personal investments",
  "Other",
];

export const REGISTERED_AGENT_OPTIONS = ["Vistra", "ILS Fiduciary", "Patton, Moreno & Asvat", "Rosemont", "Other"];

export const NAME_CHECK_STATUS_OPTIONS = ["Not Submitted", "Submitted to Vistra", "Name Confirmed", "Rejected"];

export const SOURCE_OF_FUNDS_OPTIONS = ["Shareholder", "Ultimate Beneficial Owner", "Capital injection", "Loan", "Third party"];

export const NATURE_OF_BUSINESS_OPTIONS = [
  "Investment holding - real estate",
  "Investment holding - financial assets",
  "Investment holding - other assets",
  "Services or product trading",
  "Other",
];

export const COMPANY_SECRETARY_OPTIONS = [
  "None",
  "Vistra entity",
  "Same as a director",
  "Same as the UBO",
  "Individual (third party)",
  "Corporate (third party)",
];

export const ENTITY_DETAIL_TYPE_OPTIONS = [
  "Company",
  "Trust",
  "Foundation",
  "Fund",
  "Limited Partnership",
  "State-Owned Enterprise",
];

export const CHARGE_STATUS_OPTIONS = ["Outstanding", "Satisfied", "Released"];

export const ACTION_POINT_STATUS_OPTIONS = ["Open", "In Progress", "Done"];

export const ACTION_POINT_PRIORITY_OPTIONS = ["High", "Medium", "Low"];

export const PEP_TYPE_OPTIONS = [
  "Domestic PEP",
  "Foreign PEP",
  "International Org PEP",
  "Family Member",
  "Close Associate",
];

export const PEP_RISK_CONCLUSION_OPTIONS = ["Proceed", "Proceed with EDD", "Decline"];

export const AR_FILING_STATUS_OPTIONS = [
  "Not Started",
  "Data Prepared",
  "Submitted to Vistra",
  "Filed",
  "Confirmed",
];

export const SCREENING_STATUS_OPTIONS = ["Not Started", "In Progress", "Cleared", "Adverse Findings"];

export const MLRO_SIGNOFF_STATUS_OPTIONS = ["Pending", "Signed Off", "Rejected"];

export const VISTRA_STATUS_OPTIONS = ["Not Submitted", "Submitted", "Query Raised", "Approved", "Rejected"];

export const SCREENING_TOOL_OPTIONS = [
  "World-Check One",
  "Dow Jones Risk & Compliance",
  "LexisNexis Bridger",
  "Manual / open-source",
  "Other",
];

export const DOCUMENT_CATEGORY_OPTIONS = [
  "CDD",
  "Activation Document",
  "Reference Letter",
  "Structure Chart",
  "Corporate Document",
  "KYC Form",
  "Filed Return / Confirmation",
  "Restoration",
  "Closure / Strike Off",
  "Other",
];

export const INSTRUCTION_STATUS_OPTIONS = ["Pending", "In Progress", "Completed", "On Hold"];

export const INVOICE_LEDGER_STATUS_OPTIONS = ["Draft", "Raised", "Paid", "Overdue"];

export const INSTRUCTION_TYPE_OPTIONS = [
  "COI Issuance",
  "COGS Issuance",
  "COI & COGS Issuance",
  "New BVI Formation",
  "Change in Directors",
  "Change in Shareholding",
  "LEI Renewal",
  "AR Filing",
  "ESR Filing",
  "ROM/RBO Filing",
  "Notarization / Apostille",
  "Transfer & Restoration to Vistra",
  "Company Closure / Strike Off",
  "Other",
];

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
