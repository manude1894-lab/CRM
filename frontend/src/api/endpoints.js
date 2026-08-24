import { api } from "./client";

// ─── Auth ──────────────────────────────────────────────────────────────
export const authApi = {
  login: (email, password) => api.post("/auth/login", { email, password }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
};

// ─── Users ─────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => api.get("/users").then((r) => r.data),
  get: (id) => api.get(`/users/${id}`).then((r) => r.data),
  create: (data) => api.post("/users", data).then((r) => r.data),
  update: (id, data) => api.patch(`/users/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/users/${id}`),
};

// ─── Cases ─────────────────────────────────────────────────────────────
export const casesApi = {
  list: (params = {}) => api.get("/cases", { params }).then((r) => r.data),
  get: (id) => api.get(`/cases/${id}`).then((r) => r.data),
  create: (data) => api.post("/cases", data).then((r) => r.data),
  update: (id, data) => api.patch(`/cases/${id}`, data).then((r) => r.data),
  changeStage: (id, stage) => api.post(`/cases/${id}/stage`, { stage }).then((r) => r.data),
  raiseInvoice: (id, amount = 0) => api.post(`/cases/${id}/invoice/raise`, { amount }).then((r) => r.data),
  markInvoicePaid: (id) => api.post(`/cases/${id}/invoice/mark-paid`).then((r) => r.data),
  delete: (id) => api.delete(`/cases/${id}`),
};

// ─── CDD / KYC ─────────────────────────────────────────────────────────
export const cddApi = {
  listAll: () => api.get("/cdd").then((r) => r.data),
  get: (caseId) => api.get(`/cdd/${caseId}`).then((r) => r.data),
  update: (caseId, data) => api.patch(`/cdd/${caseId}`, data).then((r) => r.data),
  review: (caseId, data) => api.post(`/cdd/${caseId}/review`, data).then((r) => r.data),
  addDocument: (caseId, data) => api.post(`/cdd/${caseId}/documents`, data).then((r) => r.data),
  updateDocument: (documentId, data) => api.patch(`/cdd/documents/${documentId}`, data).then((r) => r.data),
  deleteDocument: (documentId) => api.delete(`/cdd/documents/${documentId}`),
};

// ─── Directors & Shareholders ──────────────────────────────────────────
export const directorsApi = {
  list: (caseId) => api.get(`/cases/${caseId}/directors`).then((r) => r.data),
  create: (caseId, data) => api.post(`/cases/${caseId}/directors`, data).then((r) => r.data),
  update: (id, data) => api.patch(`/directors/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/directors/${id}`),
};

export const shareholdersApi = {
  list: (caseId) => api.get(`/cases/${caseId}/shareholders`).then((r) => r.data),
  create: (caseId, data) => api.post(`/cases/${caseId}/shareholders`, data).then((r) => r.data),
  update: (id, data) => api.patch(`/shareholders/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/shareholders/${id}`),
};

// ─── Instructions (service-request tracker) ───────────────────────────
export const instructionsApi = {
  list: (params = {}) => api.get("/instructions", { params }).then((r) => r.data),
  get: (id) => api.get(`/instructions/${id}`).then((r) => r.data),
  create: (data) => api.post("/instructions", data).then((r) => r.data),
  update: (id, data) => api.patch(`/instructions/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/instructions/${id}`),
};

// ─── Invoices (running ledger of charges) ─────────────────────────────
export const invoicesApi = {
  list: (params = {}) => api.get("/invoices", { params }).then((r) => r.data),
  get: (id) => api.get(`/invoices/${id}`).then((r) => r.data),
  create: (data) => api.post("/invoices", data).then((r) => r.data),
  update: (id, data) => api.patch(`/invoices/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/invoices/${id}`),
};

// ─── Compliance ────────────────────────────────────────────────────────
export const complianceApi = {
  listUpcoming: (days = 60) => api.get("/compliance", { params: { days } }).then((r) => r.data),
  get: (caseId) => api.get(`/compliance/${caseId}`).then((r) => r.data),
  markDone: (caseId, item) => api.post(`/compliance/${caseId}/mark-done`, { item }).then((r) => r.data),
};

// ─── Notifications ─────────────────────────────────────────────────────
export const notificationsApi = {
  list: (params = {}) => api.get("/notifications", { params }).then((r) => r.data),
  unreadCount: () => api.get("/notifications/unread-count").then((r) => r.data),
  markRead: (id) => api.post(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () => api.post("/notifications/read-all").then((r) => r.data),
};

// ─── Accounts ──────────────────────────────────────────────────────────
export const accountsApi = {
  list: (params = {}) => api.get("/accounts", { params }).then((r) => r.data),
  get: (id) => api.get(`/accounts/${id}`).then((r) => r.data),
  create: (data) => api.post("/accounts", data).then((r) => r.data),
  update: (id, data) => api.patch(`/accounts/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/accounts/${id}`),
};

// ─── Activities ────────────────────────────────────────────────────────
export const activitiesApi = {
  list: (params = {}) => api.get("/activities", { params }).then((r) => r.data),
  get: (id) => api.get(`/activities/${id}`).then((r) => r.data),
  create: (data) => api.post("/activities", data).then((r) => r.data),
  update: (id, data) => api.patch(`/activities/${id}`, data).then((r) => r.data),
  delete: (id) => api.delete(`/activities/${id}`),
};

// ─── Dashboard ─────────────────────────────────────────────────────────
export const dashboardApi = {
  get: () => api.get("/dashboard").then((r) => r.data),
};

// ─── Reports (PDF) ─────────────────────────────────────────────────────
export const reportsApi = {
  download: async (reportType) => {
    const res = await api.get(`/reports/${reportType}`, { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${reportType}-${new Date().toISOString().split("T")[0]}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};
