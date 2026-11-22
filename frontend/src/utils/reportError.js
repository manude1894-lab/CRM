// Review 22-11-2026 (package 6): a crash in the browser is reported to the server, which logs it and alerts the
// support desk. Plain fetch (not the API client) so a broken sign-in or token refresh cannot stop the report.
// The same error is reported once per page load; no client data is sent, only the page and the error.
import { API_URL } from "../api/client";

const sent = new Set();

export function reportError(where, error, stack) {
  try {
    const errorType = String(error?.name || "Error").slice(0, 100);
    const message = String(error?.message || error || "").slice(0, 1000);
    const key = `${where}|${errorType}|${message}`;
    if (sent.has(key) || sent.size >= 20) return Promise.resolve(null);
    sent.add(key);
    return fetch(`${API_URL}/system/client-errors`, {
      method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
      body: JSON.stringify({ where: String(where).slice(0, 300), error_type: errorType, message,
        stack: String(stack || error?.stack || "").slice(0, 4000) || null }),
    }).then((r) => (r.ok ? r.json() : null)).then((d) => d?.reference || null).catch(() => null);
  } catch {
    return Promise.resolve(null);
  }
}

// Errors outside a page (event handlers, promises nobody waited for).
export function watchGlobalErrors() {
  window.addEventListener("error", (e) => { if (e.error) reportError("window", e.error); });
  window.addEventListener("unhandledrejection", (e) => {
    const r = e.reason;
    if (r?.isAxiosError || r?.response) return; // server answers are already handled on screen
    reportError("promise", r instanceof Error ? r : new Error(String(r)));
  });
}
