import React, { useEffect, useState } from "react";
import { caseComplianceApi } from "../../api/endpoints";
import { toast } from "../../store/toast";
import { formatTimestamp } from "../../utils/auditFormat";
import { ChangeList, DecisionButtons, DecisionNote, REQUEST_TYPE_LABEL } from "../compliance/ComplianceParts";

export const COMPLIANCE_STYLE = {
  "Pending Approval": "bg-amber-100 text-amber-800",
  Returned: "bg-red-50 text-red-700",
  Approved: "bg-emerald-50 text-emerald-700",
};

/** Small chip for case cards and tables; nothing is shown once a case is approved. */
export function CaseComplianceChip({ status }) {
  if (!status || status === "Approved") return null;
  return <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${COMPLIANCE_STYLE[status]}`}>Compliance: {status}</span>;
}

/**
 * Compliance state of a case: a new case waits for CO / MLRO approval before it can move through the
 * pipeline, and edits to an approved case wait as a "case amendment" until approved.
 */
export default function CaseComplianceBar({ caseId, refreshKey, onChanged }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => caseComplianceApi.get(caseId).then(setState).catch(() => setState(null));
  useEffect(() => { if (caseId) load(); }, [caseId, refreshKey]);
  if (!state) return null;

  const req = state.request;
  const lastDecision = state.history.find((h) => h.status === "Rejected" || h.status === "Withdrawn");
  const act = async (action, body) => {
    setBusy(true);
    try {
      setState(await caseComplianceApi.act(caseId, action, body));
      toast.success({ approve: "Approved", reject: "Rejected and returned to the maker", withdraw: "Withdrawn", resubmit: "Resubmitted to Compliance" }[action]);
      onChanged?.();
      return true;
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
      return false;
    } finally { setBusy(false); }
  };

  const tone = req ? "border-amber-200 bg-amber-50" : state.compliance_status === "Returned" ? "border-red-200 bg-red-50/50" : "border-gray-100 bg-white";
  return (
    <div className={`mb-3 rounded-lg border ${tone}`}>
      <div className="flex flex-wrap items-start gap-2 px-3 py-2">
        <div className="flex-1 min-w-[220px]">
          <div className="text-xs font-semibold text-gray-800 flex items-center gap-2">
            Compliance
            <span className={`px-2 py-0.5 rounded ${COMPLIANCE_STYLE[state.compliance_status] || "bg-gray-100 text-gray-600"}`}>{state.compliance_status}</span>
          </div>
          <div className="text-[11px] text-gray-600 mt-0.5">
            {req ? <>{REQUEST_TYPE_LABEL[req.request_type]} submitted by {req.maker_name || "—"} {formatTimestamp(req.submitted_at)} — locked until Compliance decides.</>
              : state.compliance_status === "Returned" ? "Returned by Compliance. Update the case and resubmit; it can't move through the pipeline until approved."
              : "Approved. Any change you save is sent to Compliance and applies once approved."}
          </div>
        </div>
        {state.actions.length > 0 && <DecisionButtons actions={state.actions} busy={busy} onAction={act} />}
      </div>
      {!req && state.compliance_status === "Returned" && lastDecision && <div className="px-3 pb-2"><DecisionNote request={lastDecision} /></div>}
      {req?.changes && <div className="border-t border-amber-100 px-3 py-2 bg-white/60"><ChangeList diff={req.changes} /></div>}
    </div>
  );
}
