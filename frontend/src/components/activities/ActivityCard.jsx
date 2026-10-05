import React from "react";
import { Icon, Badge } from "../ui";
import { fmtDate } from "../../utils/constants";

const TYPE_COLORS = {
  "Visit Report": "#1a3a5c", "Call Report": "#0f766e", Meeting: "#334e68", Demo: "#8b5cf6", Call: "#10b981",
  Email: "#94a3b8", "Follow-up": "#f59e0b", Note: "#64748b",
};

/** One activity / Visit Report / Call Report in a list. */
export default function ActivityCard({ activity: a, onEdit, onDelete, compact = false }) {
  const report = a.activity_type === "Visit Report" || a.activity_type === "Call Report";
  return (
    <div className={`bg-white border border-gray-100 rounded-xl ${compact ? "p-3" : "p-4 shadow-sm hover:shadow-md"} transition-shadow flex gap-3`}>
      <div className="flex-shrink-0">
        <div className="w-9 h-9 rounded-full flex items-center justify-center text-white text-[11px] font-bold"
          style={{ background: TYPE_COLORS[a.activity_type] || "#94a3b8" }}>
          {report ? (a.activity_type === "Visit Report" ? "VR" : "CR") : a.activity_type[0]}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            {!compact && <span className="font-semibold text-sm text-gray-800">{a.company_name}</span>}
            <Badge text={a.activity_type} />
            <span className="text-xs text-gray-400">{a.activity_uid}</span>
            {a.status !== "Completed" && <span className="text-[11px] text-gray-500">{a.status}</span>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400 whitespace-nowrap">{fmtDate(a.activity_date)}</span>
            {onEdit && (
              <button onClick={onEdit} title="Edit" className="p-1 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600"><Icon name="edit" size={13} /></button>
            )}
            {onDelete && (
              <button onClick={onDelete} title="Delete" className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={13} /></button>
            )}
          </div>
        </div>
        {report && (
          <div className="text-xs text-gray-500 mb-1">
            {a.activity_type === "Visit Report" ? "Met" : "Spoke to"} <strong className="text-gray-700">{a.client_contact}</strong>
            {a.location && <> at {a.location}</>}{a.attendees && <> · Triam: {a.attendees}</>}{a.purpose && <> · {a.purpose}</>}
          </div>
        )}
        <p className="text-sm text-gray-700 mb-1 whitespace-pre-line">{a.summary}</p>
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          {a.outcome && <span><strong className="text-gray-600">Outcome:</strong> {a.outcome}</span>}
          {a.next_action && <span><strong className="text-gray-600">Next:</strong> {a.next_action}{a.due_date ? ` (by ${fmtDate(a.due_date)})` : ""}</span>}
        </div>
      </div>
    </div>
  );
}
