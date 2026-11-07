// Turning raw audit rows into readable text (BRD §13/§15 audit trail). Pure — unit-tested.

const FIELD_LABELS = {
  spoc_id: "Anchor RM",
  non_anchor_rm_ids: "Non-anchor RMs",
  owner_id: "Created by",
  anchor_entity: "Anchor Triam Entity",
  non_anchor_entities: "Non-anchor Triam Entities",
  company_name: "Name",
  registration_number: "Incorporation Certificate No.",
  trn_vat_number: "TRN / VAT No.",
  is_pep: "PEP",
  supervisor_id: "Supervisor",
  business_role_id: "Business role",
};

// "license_expiry_date" -> "License expiry date"
export const fieldLabel = (key) =>
  FIELD_LABELS[key] || key.replace(/_ids?$/, "").replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function formatValue(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.length ? v.map(formatValue).join(", ") : "—";
  if (typeof v === "object") return Object.entries(v).filter(([, x]) => x).map(([k, x]) => `${fieldLabel(k)}: ${formatValue(x)}`).join("; ") || "—";
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}/.test(v)) {
    const [y, m, d] = v.slice(0, 10).split("-");
    return `${d} ${m} ${y}`; // BRD §14 — DD MM YYYY
  }
  return String(v);
}

// [{field, from, to}] for an update row; creates list the initial values; deletes have none.
export function changeLines(entry) {
  const changes = entry?.changes || {};
  if (entry?.action === "create") {
    return Object.entries(changes).map(([field, value]) => ({ field: fieldLabel(field), from: null, to: formatValue(value) }));
  }
  return Object.entries(changes)
    .filter(([, pair]) => Array.isArray(pair) && pair.length === 2)
    .map(([field, [from, to]]) => ({ field: fieldLabel(field), from: formatValue(from), to: formatValue(to) }));
}

export const ACTION_LABELS = {
  country_add: "Country added",
  country_update: "Country changed",
  create: "Created",
  update: "Updated",
  delete: "Deleted",
  login: "Logged in",
  login_failed: "Failed login",
  password_change: "Password changed",
  password_reset_request: "Password reset requested",
  password_reset: "Password reset",
  // Prospects and the new-client approval flow
  assign: "Assigned",
  duplicate_override: "Duplicate name allowed",
  submit: "Submitted for approval",
  cdd_update: "CDD updated",
  compliance_approve: "Compliance approved",
  approve: "Approved",
  reject: "Rejected",
  withdraw: "Withdrawn",
  // Existing clients: amendments and status
  amend_start: "Amendment started",
  amend_submit: "Amendment submitted",
  amend_approve: "Amendment approved",
  amend_reject: "Amendment rejected",
  amend_withdraw: "Amendment withdrawn",
  amend_discard: "Amendment discarded",
  activate: "Activated",
  deactivate: "Marked inactive",
  reactivate: "Reactivated",
  mark_exit: "Marked for exit",
  cancel_exit: "Exit cancelled",
  confirm_exit: "Exited",
  // Documents and invoices
  document_upload: "Document added",
  document_delete: "Document removed",
  document_download: "Document downloaded",
  invoice_request_draft: "Invoice request drafted",
  invoice_request: "Invoice requested",
  invoice_raise: "Invoice raised",
  invoice_paid: "Invoice paid",
};

export function formatTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())} ${pad(d.getMonth() + 1)} ${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
