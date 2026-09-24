import React, { useEffect, useState } from "react";

// Debounced, non-blocking fuzzy-duplicate advisory — never prevents saving.
// onSelect (optional): lets the user jump straight into amending an existing match
// instead of typing a fresh record (client CRM-change-request item 1).
export default function DuplicateWarning({ name, excludeId, checkFn, active, onSelect }) {
  const [matches, setMatches] = useState([]);

  useEffect(() => {
    if (!active || !name || name.trim().length < 3) {
      setMatches([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        setMatches(await checkFn(name.trim(), excludeId));
      } catch {
        setMatches([]);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [name, excludeId, active]);

  if (matches.length === 0) return null;

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3 text-xs text-amber-700">
      <p className="font-medium mb-1">Possible duplicate{matches.length > 1 ? "s" : ""}:</p>
      {matches.map((m) => (
        <div key={`${m.source || ""}-${m.id}`} className="flex items-center justify-between gap-2">
          <span>{m.company_name} — {m.score}% match{m.source === "client" ? " (existing client)" : ""}</span>
          {onSelect && (
            <button type="button" onClick={() => onSelect(m.id)} className="text-amber-800 underline hover:no-underline flex-shrink-0">
              Amend this client
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
