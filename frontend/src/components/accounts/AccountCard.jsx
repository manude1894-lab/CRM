import React from "react";
import { Badge } from "../ui";
import { fmtDate } from "../../utils/constants";

/** One client tile on the Clients page (card view). Clicking it opens the client's page. */
export default function AccountCard({ account: a, anchorRm, isSelected, onOpen, onToggleSelected }) {
  const facts = [
    ["Anchor RM", anchorRm],
    ["Risk", a.risk_rating],
    ["Next AML review", fmtDate(a.next_aml_review_date)],
  ];
  return (
    <div onClick={onOpen}
      className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm cursor-pointer hover:shadow-md hover:border-brand-200 transition-all">
      <div className="flex items-start gap-3">
        <input type="checkbox" checked={isSelected} onClick={(e) => e.stopPropagation()} onChange={onToggleSelected} className="mt-1" />
        <div className="w-10 h-10 rounded-xl flex-shrink-0 flex items-center justify-center text-white font-bold text-sm" style={{ background: "#1a3a5c" }}>
          {a.company_name.slice(0, 2).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-sm font-bold text-gray-800 truncate">{a.company_name}</h3>
            <Badge text={a.profile_status || "New"} />
          </div>
          <p className="text-[11px] font-mono text-gray-400">{a.client_id || `Temp ${a.account_uid}`}</p>
          <p className="text-xs text-gray-500 truncate">
            {a.account_type === "Individual" ? `Individual · ${a.nationality || "—"}` : `${a.industry || "—"} · ${a.country || "—"}`}
          </p>
        </div>
      </div>
      <dl className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-gray-50">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[10px] uppercase tracking-wide text-gray-400">{label}</dt>
            <dd className="text-xs font-medium text-gray-700 truncate">{value || "—"}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
