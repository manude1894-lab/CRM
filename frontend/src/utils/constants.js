// Where a prospect came from.
export const PROSPECT_SOURCE_OPTIONS = ["Senior Mgmt", "Social Media", "Referral", "Other"];

// Amounts without their own currency are in AED (Triam bills in the UAE; invoices carry their own currency).
export const fmtFull = (n) => `AED ${Number(n || 0).toLocaleString()}`;

// CSV/export filenames: "<base>_YYYY-MM-DD_HH-mm-ss.csv" so every export is
// timestamped and never silently overwrites the last one in the Downloads folder.
export const exportFilename = (base, ext = "csv") => {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const time = `${pad(d.getHours())}-${pad(d.getMinutes())}-${pad(d.getSeconds())}`;
  return `${base}_${date}_${time}.${ext}`;
};

// Country dropdowns are fed by the Countries master, where the UAE is "United Arab
// Emirates (the)"; older/free-text records may hold "UAE". Accept both.
export const isUAE = (country) => country === "UAE" || (country || "").startsWith("United Arab Emirates");

// BRD §12 — display dates as DD MM YYYY everywhere.
// Date entry uses the shared <DateInput> (components/ui), which shows DD MM YYYY on every computer.
export const fmtDate = (d) => {
  if (!d) return "";
  const s = String(d).slice(0, 10);
  const [y, m, day] = s.split("-");
  if (!y || !m || !day) return s;
  return `${day} ${m} ${y}`;
};

export const ROLE_LABEL = {
  admin: "Admin",
  rm: "Staff",
};

// Labels for the system role on the user form: what kind of user, separate from the business role
// (MLRO, Approver, Accountant …) that carries the permissions.
// Users who can be a client's RM: active client-facing staff (RM, RO, FO, Sales Manager …), not the
// central desks (Compliance, Approver, Accounts, Inquiry, Prospecting Coordinator) or administrators.
export const isRelationshipManager = (u) => u.role === "rm" && u.handles_clients !== false && u.is_active !== false;

export const USER_TYPE_LABEL = {
  rm: "Standard user",
  admin: "Administrator",
};

export const PROSPECT_STATUS_OPTIONS = ["New", "Proposal Sent", "Negotiating", "Won", "Lost"];

// ─── Client profile (BRD §4–§9) ──────────────────────────────────────────
export const REGULATOR_OPTIONS = ["DFSA", "FSRA", "CMA", "UAECB", "Other"];

export const TAG_OPTIONS = ["DIFC", "ADGM", "DNFBP", "Mainland", "Holding Co.", "SPV"];

// Triam's own legal entities (BRD §4); the Triam Entities master list is the source, this is the fallback.
export const TRIAM_ENTITY_OPTIONS = ["TCPL", "TMCL", "IFZA", "TABL", "TCDL"];

export const SERVICES_OBTAINED_OPTIONS = [
  "Company Formation",
  "Corporate Secretarial",
  "Accounting & Bookkeeping",
  "VAT Registration & Filing",
  "Corporate Tax Registration & Filing",
  "Compliance & AML Advisory",
  "Registered Agent Services",
  "Trust & Fiduciary Services",
  "Licensing & Regulatory Support",
  "Other",
];

export const PROFILE_STATUS_OPTIONS = [
  "New", "WIP", "Awaiting Approval", "Approved", "Active", "Inactive", "Marked for Exit", "Exited",
];

// Country calling codes for the split Contact Mobile field (BRD §5) — UAE first, then the GCC and
// major markets.
export const COUNTRY_CALLING_CODES = [
  { code: "+971", label: "+971 (UAE)" },
  { code: "+966", label: "+966 (Saudi Arabia)" },
  { code: "+974", label: "+974 (Qatar)" },
  { code: "+973", label: "+973 (Bahrain)" },
  { code: "+968", label: "+968 (Oman)" },
  { code: "+965", label: "+965 (Kuwait)" },
  { code: "+1284", label: "+1284 (BVI)" },
  { code: "+1345", label: "+1345 (Cayman Islands)" },
  { code: "+248", label: "+248 (Seychelles)" },
  { code: "+44", label: "+44 (UK / Jersey / Guernsey / Isle of Man)" },
  { code: "+230", label: "+230 (Mauritius)" },
  { code: "+1", label: "+1 (US / Canada)" },
  { code: "+91", label: "+91 (India)" },
  { code: "+65", label: "+65 (Singapore)" },
  { code: "+86", label: "+86 (China)" },
  { code: "+81", label: "+81 (Japan)" },
  { code: "+852", label: "+852 (Hong Kong)" },
  { code: "+27", label: "+27 (South Africa)" },
  { code: "+20", label: "+20 (Egypt)" },
  { code: "+961", label: "+961 (Lebanon)" },
  { code: "+962", label: "+962 (Jordan)" },
  { code: "+90", label: "+90 (Turkey)" },
  { code: "+33", label: "+33 (France)" },
  { code: "+49", label: "+49 (Germany)" },
  { code: "+41", label: "+41 (Switzerland)" },
  { code: "+39", label: "+39 (Italy)" },
  { code: "+34", label: "+34 (Spain)" },
  { code: "+31", label: "+31 (Netherlands)" },
  { code: "+353", label: "+353 (Ireland)" },
  { code: "+61", label: "+61 (Australia)" },
  { code: "+64", label: "+64 (New Zealand)" },
  { code: "+92", label: "+92 (Pakistan)" },
  { code: "+880", label: "+880 (Bangladesh)" },
  { code: "+94", label: "+94 (Sri Lanka)" },
  { code: "+63", label: "+63 (Philippines)" },
  { code: "+60", label: "+60 (Malaysia)" },
  { code: "+62", label: "+62 (Indonesia)" },
  { code: "+7", label: "+7 (Russia)" },
  { code: "+55", label: "+55 (Brazil)" },
];

// Today as "Fri 09 10 2026" for the top bar (DD MM YYYY, independent of the PC's region).
export const fmtToday = (now = new Date()) => {
  const pad = (n) => String(n).padStart(2, "0");
  const day = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][now.getDay()];
  return `${day} ${pad(now.getDate())} ${pad(now.getMonth() + 1)} ${now.getFullYear()}`;
};

// CSV dates as DD/MM/YYYY, which Excel set to UAE / UK format reads as dates. Timestamps add HH:MM.
export const csvDate = (v) => {
  if (v === null || v === undefined || v === "") return v;
  const s = String(v);
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/);
  if (!m) return v;
  return `${m[3]}/${m[2]}/${m[1]}${m[4] && s.length > 10 ? ` ${m[4]}:${m[5]}` : ""}`;
};
