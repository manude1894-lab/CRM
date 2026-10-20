import { api } from "./client";

// ─── Auth ──────────────────────────────────────────────────────────────
export const authApi = {
  login: (email, password) => api.post("/auth/login", { email, password }).then((r) => r.data),
  changePassword: (current_password, new_password) => api.post("/auth/change-password", { current_password, new_password }),
  me: () => api.get("/auth/me").then((r) => r.data),
};

// ─── Users ─────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => api.get("/users").then((r) => r.data),
  get: (id) => api.get(`/users/${id}`).then((r) => r.data),
  create: (data) => api.post("/users", data).then((r) => r.data),
  update: (id, data) => api.patch(`/users/${id}`, data).then((r) => r.data),
  remove: (id) => api.delete(`/users/${id}`), // support account only
};

export const departmentsApi = {
  list: () => api.get("/departments").then((r) => r.data),
  create: (data) => api.post("/departments", data).then((r) => r.data),
  update: (id, data) => api.patch(`/departments/${id}`, data).then((r) => r.data),
};

// ─── Master data, roles, audit (BRD §13, §17) ─────────────────────────
export const mastersApi = {
  types: () => api.get("/masters").then((r) => r.data),
  list: (listType, includeInactive = false) =>
    api.get(`/masters/${listType}`, { params: { include_inactive: includeInactive } }).then((r) => r.data),
  create: (listType, data) => api.post(`/masters/${listType}`, data).then((r) => r.data),
  update: (itemId, data) => api.patch(`/masters/items/${itemId}`, data).then((r) => r.data),
};

export const rolesApi = {
  permissions: () => api.get("/roles/permissions").then((r) => r.data),
  list: () => api.get("/roles").then((r) => r.data),
  create: (data) => api.post("/roles", data).then((r) => r.data),
  update: (id, data) => api.patch(`/roles/${id}`, data).then((r) => r.data),
};

export const auditApi = {
  list: (params = {}) => api.get("/audit", { params }).then((r) => ({ items: r.data, total: +(r.headers["x-total-count"] || r.data.length) })),
  forAccount: (accountId, params = {}) =>
    api.get(`/accounts/${accountId}/audit`, { params }).then((r) => ({ items: r.data, total: +(r.headers["x-total-count"] || r.data.length) })),
  // Activity report (BRD §2): the log with the same filters, as a CSV file
  exportCsv: async (params = {}) => {
    const res = await api.get("/audit/export", { params, responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `triam-crm-activity-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};

// ─── New-client approval: RM → Compliance (MLRO) → Approver (BRD §7–§10) ──
export const workflowApi = {
  get: (accountId) => api.get(`/accounts/${accountId}/workflow`).then((r) => r.data),
  submit: (accountId, comment, kycDeclared) => api.post(`/accounts/${accountId}/submit`, { comment: comment || null, kyc_declared: !!kycDeclared }).then((r) => r.data),
  approve: (accountId, comment) => api.post(`/accounts/${accountId}/approve`, { comment: comment || null }).then((r) => r.data),
  reject: (accountId, reason_code, reason_text) => api.post(`/accounts/${accountId}/reject`, { reason_code, reason_text }).then((r) => r.data),
  withdraw: (accountId) => api.post(`/accounts/${accountId}/withdraw`).then((r) => r.data),
  status: (accountId, action, reason) => api.post(`/accounts/${accountId}/status`, { action, reason: reason || null }).then((r) => r.data),
  inbox: (status = "Pending", request_type) => api.get("/approvals", { params: { status, request_type: request_type || undefined } }).then((r) => r.data),
};

// ─── Client amendments (BRD §11) ─────────────────────────────────────
export const amendmentApi = {
  get: (accountId) => api.get(`/accounts/${accountId}/amendment`).then((r) => r.data),
  start: (accountId) => api.post(`/accounts/${accountId}/amendment`).then((r) => r.data),
  // action: submit | approve | reject | withdraw | discard; body: { comment } or { reason_code, reason_text }
  act: (accountId, action, body = {}) => api.post(`/accounts/${accountId}/amendment/${action}`, body).then((r) => r.data),
};

// ─── Client parties: Shareholders / UBOs, Directors, Authorised Signatories, joint holders ──
export const accountPartiesApi = {
  list: (accountId) => api.get(`/accounts/${accountId}/parties`).then((r) => r.data),
  create: (accountId, data) => api.post(`/accounts/${accountId}/parties`, data).then((r) => r.data),
  // accountId is only needed for a party added in an open amendment (negative id, not saved yet).
  update: (id, data, accountId) => api.patch(`/account-parties/${id}`, data, { params: { account_id: accountId } }).then((r) => r.data),
  remove: (id, accountId, reason) => api.post(`/account-parties/${id}/remove`, { reason }, { params: { account_id: accountId } }),
  removed: (accountId) => api.get(`/accounts/${accountId}/removed-parties`).then((r) => r.data),
};

// ─── Service Requests (BRD §15) ────────────────────────────────────────
export const instructionsApi = {
  list: (params = {}) => api.get("/instructions", { params }).then((r) => r.data),
  options: (triamEntity) => api.get("/instructions/options", { params: triamEntity ? { triam_entity: triamEntity } : {} }).then((r) => r.data),
  get: (id) => api.get(`/instructions/${id}`).then((r) => r.data),
  create: (data) => api.post("/instructions", data).then((r) => r.data),
  update: (id, data) => api.patch(`/instructions/${id}`, data).then((r) => r.data),
  cancel: (id, reason) => api.post(`/instructions/${id}/cancel`, { reason }),
};

// ─── Invoices (BRD §16) ────────────────────────────────────────────────
export const invoicesApi = {
  list: (params = {}) => api.get("/invoices", { params }).then((r) => r.data),
  get: (id) => api.get(`/invoices/${id}`).then((r) => r.data),
  create: (data) => api.post("/invoices", data).then((r) => r.data),
  update: (id, data) => api.patch(`/invoices/${id}`, data).then((r) => r.data),
  cancel: (id, reason) => api.post(`/invoices/${id}/cancel`, { reason }),
  request: (data) => api.post("/invoices/request", data).then((r) => r.data),
  raise: (id, data) => api.post(`/invoices/${id}/raise`, data).then((r) => r.data),
  paid: (id, data = {}) => api.post(`/invoices/${id}/paid`, data).then((r) => r.data),
  attachments: (id) => api.get(`/invoices/${id}/attachments`).then((r) => r.data),
  attach: (id, file, kind) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);
    return api.post(`/invoices/${id}/attachments`, fd, { headers: { "Content-Type": "multipart/form-data" } }).then((r) => r.data);
  },
};

// ─── Countries master (BRD §17) ──────────────────────────────────────
export const countriesApi = {
  list: () => api.get("/countries").then((r) => r.data),
  create: (data) => api.post("/countries", data).then((r) => r.data),
  update: (id, data) => api.patch(`/countries/${id}`, data).then((r) => r.data),
};

// ─── Client document folder (BRD §14) ─────────────────────────────────
export const documentsApi = {
  listForAccount: (accountId) => api.get(`/accounts/${accountId}/documents`).then((r) => r.data),
  // The client folder: documents by category, their stage and whether this user may remove them
  folder: (accountId) => api.get(`/accounts/${accountId}/folder`).then((r) => r.data),
  addLink: (accountId, data) => api.post(`/accounts/${accountId}/documents/link`, data).then((r) => r.data),
  uploadForAccount: (accountId, formData) =>
    api.post(`/accounts/${accountId}/documents`, formData, { headers: { "Content-Type": undefined } }).then((r) => r.data),
  remove: (id, reason) => api.post(`/documents/${id}/remove`, { reason: reason || null }),
  download: async (id, filename) => {
    const res = await api.get(`/documents/${id}/download`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `document-${id}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
  view: async (id) => {
    // Same bytes as download; window.open renders them by MIME type (blob URL has
    // no Content-Disposition). Works for PDFs and images.
    const res = await api.get(`/documents/${id}/download`, { responseType: "blob" });
    const url = window.URL.createObjectURL(res.data);
    window.open(url, "_blank", "noopener");
    setTimeout(() => window.URL.revokeObjectURL(url), 60000);
  },
};

// ─── Notifications ─────────────────────────────────────────────────────
export const notificationsApi = {
  list: (params = {}) => api.get("/notifications", { params }).then((r) => r.data),
  unreadCount: () => api.get("/notifications/unread-count").then((r) => r.data),
  markRead: (id) => api.post(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () => api.post("/notifications/read-all").then((r) => r.data),
};

// ─── Clients ───────────────────────────────────────────────────────────
export const accountsApi = {
  list: (params = {}) => api.get("/accounts", { params }).then((r) => r.data),
  get: (id) => api.get(`/accounts/${id}`).then((r) => r.data),
  create: (data) => api.post("/accounts", data).then((r) => r.data),
  update: (id, data) => api.patch(`/accounts/${id}`, data).then((r) => r.data),
  import: (rows, dryRun) => api.post("/accounts/import", { rows, dry_run: dryRun }).then((r) => r.data),
  // BRD §3 — names matching the first 3+ letters (all clients; can_open says whether the user may open it)
  lookup: (q, excludeId) => api.get("/accounts/lookup", { params: { q, exclude_id: excludeId || undefined } }).then((r) => r.data),
  // Mandatory fields still missing (enforced at Submit)
  completeness: (id) => api.get(`/accounts/${id}/completeness`).then((r) => r.data),
  checkDuplicate: (name, excludeId) => api.get("/accounts/check-duplicate", { params: { name, exclude_id: excludeId || undefined } }).then((r) => r.data),
  bulkUpdate: (payload) => api.patch("/accounts/bulk", payload).then((r) => r.data),
};

// ─── Visit / Call Reports (BRD §15) ────────────────────────────────────
export const activitiesApi = {
  list: (params = {}) => api.get("/activities", { params }).then((r) => r.data),
  get: (id) => api.get(`/activities/${id}`).then((r) => r.data),
  create: (data) => api.post("/activities", data).then((r) => r.data),
  update: (id, data) => api.patch(`/activities/${id}`, data).then((r) => r.data),
  cancel: (id, reason) => api.post(`/activities/${id}/cancel`, { reason }),
};

// ─── Dashboard ─────────────────────────────────────────────────────────
export const dashboardApi = {
  get: () => api.get("/dashboard").then((r) => r.data),
  myWork: () => api.get("/dashboard/my-work").then((r) => r.data),
};

// ─── Prospects (BRD §4A) ───────────────────────────────────────────────
export const prospectsApi = {
  list: (status) => api.get("/prospects", { params: status ? { status } : {} }).then((r) => r.data),
  get: (id) => api.get(`/prospects/${id}`).then((r) => r.data),
  create: (data) => api.post("/prospects", data).then((r) => r.data),
  update: (id, data) => api.patch(`/prospects/${id}`, data).then((r) => r.data),
  assign: (id, data) => api.post(`/prospects/${id}/assign`, data).then((r) => r.data),
  checkDuplicate: (name, excludeId) => api.get("/prospects/check-duplicate", { params: { name, exclude_id: excludeId || undefined } }).then((r) => r.data),
};

// ─── Standard reports (BRD §20) — shown on screen, exported to CSV ──────
export const reportsApi = {
  standardList: () => api.get("/reports/standard").then((r) => r.data),
  standard: (key, params = {}) => api.get(`/reports/standard/${key}`, { params }).then((r) => r.data),
};

// ─── System (go-live checks) ───────────────────────────────────────────
export const systemApi = {
  healthChecks: () => api.get("/system/health-checks").then((r) => r.data),
};
