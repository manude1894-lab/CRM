import React, { useEffect, useState } from "react";
import { accountsApi } from "../../api/endpoints";

/**
 * Mandatory fields still missing (BRD §5/§9/§10/§11), grouped by section. Informational now;
 * in P2 the Submit button is blocked until this list is empty. `refreshKey` changes after each
 * save so the list stays current.
 */
export default function CompletenessChecklist({ accountId, refreshKey }) {
  const [state, setState] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!accountId) return;
    accountsApi.completeness(accountId).then(setState).catch(() => setState(null));
  }, [accountId, refreshKey]);

  if (!accountId || !state) return null;
  if (state.complete) {
    return <div className="mb-3 px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-700">All mandatory fields are complete.</div>;
  }
  const bySection = state.missing.reduce((acc, m) => ({ ...acc, [m.section]: [...(acc[m.section] || []), m.label] }), {});
  return (
    <div className="mb-3 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
      <button type="button" onClick={() => setOpen((o) => !o)} className="w-full flex items-center justify-between font-medium">
        <span>{state.missing.length} mandatory field{state.missing.length !== 1 ? "s" : ""} still missing — needed before the profile can be submitted</span>
        <span>{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1">
          {Object.entries(bySection).map(([section, labels]) => (
            <div key={section}><span className="font-semibold">{section}:</span> {labels.join(", ")}</div>
          ))}
        </div>
      )}
    </div>
  );
}
