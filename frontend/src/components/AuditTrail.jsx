import React, { useState } from "react";
import { changeLines, formatTimestamp, ACTION_LABELS } from "../utils/auditFormat";

const ACTION_STYLE = {
  create: "bg-emerald-50 text-emerald-700",
  update: "bg-brand-50 text-brand-700",
  delete: "bg-red-50 text-red-600",
  login_failed: "bg-amber-50 text-amber-700",
};

function Entry({ e }) {
  const [open, setOpen] = useState(false);
  const lines = changeLines(e);
  return (
    <div className="border-b border-gray-50 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${ACTION_STYLE[e.action] || "bg-gray-100 text-gray-600"}`}>
              {ACTION_LABELS[e.action] || e.action}
            </span>
            <span className="text-xs text-gray-700">{e.summary}</span>
          </div>
          <p className="text-[11px] text-gray-400 mt-0.5">{e.user_name || "System"} · {formatTimestamp(e.occurred_at)}</p>
        </div>
        {lines.length > 0 && (
          <button onClick={() => setOpen((o) => !o)} className="text-[11px] text-brand-600 hover:underline flex-shrink-0">
            {open ? "Hide" : `${lines.length} field${lines.length !== 1 ? "s" : ""}`}
          </button>
        )}
      </div>
      {open && (
        <table className="mt-2 w-full text-[11px]">
          <tbody>
            {lines.map((l) => (
              <tr key={l.field} className="align-top">
                <td className="py-0.5 pr-3 text-gray-500 whitespace-nowrap">{l.field}</td>
                {l.from !== null && <td className="py-0.5 pr-3 text-gray-400 line-through break-all">{l.from}</td>}
                <td className="py-0.5 text-gray-800 break-all" colSpan={l.from === null ? 2 : 1}>{l.to}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// Read-only list of audit entries (BRD §13/§15). Fetching is the caller's job.
export default function AuditTrail({ entries, loading, emptyText = "No history recorded yet." }) {
  if (loading) return <p className="text-xs text-gray-400">Loading…</p>;
  if (!entries?.length) return <p className="text-xs text-gray-400 italic">{emptyText}</p>;
  return <div>{entries.map((e) => <Entry key={e.id} e={e} />)}</div>;
}
