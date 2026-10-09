import React, { useEffect, useState } from "react";
import { systemApi } from "../../api/endpoints";
import { Spinner, ErrorBanner } from "../ui";

const SEVERITY = { high: "Must fix before go-live", medium: "Fix before go-live", low: "When available" };

/** Admin → System Health: the go-live security and configuration checks (P7). */
export default function SystemHealthPanel() {
  const [checks, setChecks] = useState(null);
  const [error, setError] = useState(null);
  const load = () => systemApi.healthChecks().then(setChecks).catch((e) => setError(e.response?.data?.detail || "Failed to load checks"));
  useEffect(() => { load(); }, []);
  if (error) return <ErrorBanner message={error} onRetry={load} />;
  if (!checks) return <Spinner />;
  const open = checks.filter((c) => !c.ok);

  return (
    <div className="space-y-3">
      <div className={`rounded-xl border px-4 py-3 text-sm ${open.some((c) => c.severity === "high") ? "border-red-200 bg-red-50 text-red-800" : open.length ? "border-amber-200 bg-amber-50 text-amber-900" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
        {open.length === 0 ? "All go-live checks pass." : `${open.length} of ${checks.length} go-live checks need attention.`}
      </div>
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm divide-y divide-gray-50">
        {checks.map((c) => (
          <div key={c.key} className="flex gap-3 px-4 py-3">
            <span className={`mt-0.5 w-5 h-5 flex-shrink-0 rounded-full text-[11px] font-bold flex items-center justify-center text-white ${c.ok ? "bg-emerald-500" : c.severity === "high" ? "bg-red-500" : c.severity === "medium" ? "bg-amber-500" : "bg-gray-400"}`}>
              {c.ok ? "✓" : "!"}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-800">{c.label}</div>
              {c.detail && <div className="text-xs text-gray-500">{c.detail}</div>}
              {!c.ok && (
                <div className="text-xs text-gray-600 mt-1">
                  <span className="font-semibold">{SEVERITY[c.severity]}:</span> {c.fix}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-gray-400">Settings such as secrets and mailbox details are set on the hosting platform, not in the CRM. They take effect after the next restart.</p>
    </div>
  );
}
