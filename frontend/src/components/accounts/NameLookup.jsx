import React, { useEffect, useState } from "react";
import { accountsApi } from "../../api/endpoints";

/**
 * BRD §3 — as the user types the 3rd letter of a client name, list existing clients whose name
 * (or Unique Search Name) has a word starting with it. An exact name match blocks an ordinary
 * duplicate; an approver may override it with a reason (BRD §3 exception route).
 *
 * props:
 *   name, excludeId, active  — what to look up, and whether to (new clients only)
 *   canOverride              — user has the client.approve permission
 *   override, onOverride     — { allow: bool, reason: string } and its setter
 *   onOpen(id)               — open an existing client the user is allowed to see
 *   onExactMatch(bool)       — tells the form whether an exact duplicate exists
 */
export default function NameLookup({ name, excludeId, active, canOverride, override, onOverride, onOpen, onExactMatch }) {
  const [matches, setMatches] = useState([]);

  useEffect(() => {
    const term = (name || "").trim();
    if (!active || term.length < 3) { setMatches([]); onExactMatch?.(false); return; }
    const timer = setTimeout(async () => {
      try {
        const rows = await accountsApi.lookup(term, excludeId);
        setMatches(rows);
        onExactMatch?.(rows.some((r) => r.exact_match));
      } catch { setMatches([]); onExactMatch?.(false); }
    }, 300);
    return () => clearTimeout(timer);
  }, [name, excludeId, active]);

  if (!matches.length) return null;
  const exact = matches.some((m) => m.exact_match);

  return (
    <div className={`border rounded-lg px-3 py-2 mb-3 text-xs ${exact ? "bg-red-50 border-red-200 text-red-700" : "bg-amber-50 border-amber-200 text-amber-800"}`}>
      <p className="font-medium mb-1">
        {exact ? "A client with this exact name already exists" : `Existing client${matches.length > 1 ? "s" : ""} with a similar name`}
      </p>
      <div className="space-y-0.5">
        {matches.map((m) => (
          <div key={m.id} className="flex items-center justify-between gap-2">
            <span className="truncate">
              <span className="font-mono text-[11px] opacity-70 mr-1.5">{m.client_id || "—"}</span>
              {m.company_name}
              {m.search_name && m.search_name !== m.company_name && <span className="opacity-60"> ({m.search_name})</span>}
              {!m.can_open && <span className="opacity-60"> · another RM's client</span>}
            </span>
            {m.can_open && onOpen && (
              <button type="button" onClick={() => onOpen(m.id)} className="underline hover:no-underline flex-shrink-0">Open / amend</button>
            )}
          </div>
        ))}
      </div>

      {exact && (canOverride ? (
        <div className="mt-2 pt-2 border-t border-red-200 space-y-1.5">
          <label className="flex items-center gap-2 font-medium">
            <input type="checkbox" checked={!!override.allow} onChange={(e) => onOverride({ ...override, allow: e.target.checked })} />
            Create anyway (approver exception)
          </label>
          {override.allow && (
            <input value={override.reason} onChange={(e) => onOverride({ ...override, reason: e.target.value })} maxLength={255}
              placeholder="Reason — e.g. separate legal entity registered in ADGM (min 10 characters)"
              className="w-full border border-red-200 rounded px-2 py-1 text-xs bg-white text-gray-800" />
          )}
        </div>
      ) : (
        <p className="mt-1.5">Open the existing client instead, or ask an approver (CO / MLRO) to create a duplicate.</p>
      ))}
    </div>
  );
}
