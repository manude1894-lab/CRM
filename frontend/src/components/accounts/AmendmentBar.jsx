import React, { useEffect, useState } from "react";
import { amendmentApi } from "../../api/endpoints";
import { toast } from "../../store/toast";
import { formatTimestamp } from "../../utils/auditFormat";
import { ChangeList, DecisionButtons, DecisionNote } from "../compliance/ComplianceParts";

/**
 * BRD §13 — existing-client maintenance. On an approved client the profile changes only through an
 * amendment: "Amend client" opens a draft, section saves go into the draft, and the maker submits it
 * to Compliance. The live record changes when a CO / MLRO approves.
 * onState(state) reports the current amendment so the form can show the staged values and decide
 * whether it is editable.
 */
export default function AmendmentBar({ accountId, refreshKey, onState, onDecided }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showChanges, setShowChanges] = useState(true);

  const apply = (s) => { setState(s); onState?.(s); };
  useEffect(() => {
    if (accountId) amendmentApi.get(accountId).then(apply).catch(() => apply(null));
  }, [accountId, refreshKey]);
  if (!state || (!state.amendable && !state.request)) return null;

  const req = state.request;
  const mineDraft = req?.status === "Draft" && state.actions.includes("submit");
  const count = state.diff?.count || 0;

  const act = async (action, body) => {
    setBusy(true);
    try {
      const next = action === "start" ? await amendmentApi.start(accountId) : await amendmentApi.act(accountId, action, body);
      apply(next);
      const msg = {
        start: "Amendment started — your changes stay in draft until Compliance approves them.",
        submit: "Amendment sent to Compliance for approval.", approve: "Amendment approved and applied.",
        reject: "Amendment rejected and returned to the maker.", withdraw: "Amendment withdrawn — it is back in draft.",
        discard: "Draft amendment discarded.",
      }[action];
      toast.success(msg);
      if (["approve", "reject", "discard", "withdraw"].includes(action)) onDecided?.(action);
      return true;
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
      return false;
    } finally { setBusy(false); }
  };

  let tone = "border-blue-100 bg-blue-50/60", title, text;
  if (!req) {
    title = "Approved client";
    text = "Changes to an approved client go to Compliance for approval. Use Amend client to start.";
  } else if (req.status === "Draft") {
    tone = "border-amber-200 bg-amber-50";
    title = mineDraft ? `Amendment in progress · ${count} change${count === 1 ? "" : "s"}` : `${req.maker_name || "Another user"} is amending this client`;
    text = mineDraft
      ? "Save sections as usual. Nothing changes on the live client until you submit and Compliance approves."
      : "The profile can't be changed by anyone else until that amendment is submitted or discarded.";
  } else {
    tone = "border-amber-300 bg-amber-50";
    title = `Amendment awaiting Compliance approval · ${count} change${count === 1 ? "" : "s"}`;
    text = `Submitted by ${req.maker_name || "—"} ${formatTimestamp(req.submitted_at)}. The client is locked until Compliance decides.`;
  }

  return (
    <div className={`mb-3 rounded-lg border ${tone}`}>
      <div className="flex flex-wrap items-start gap-2 px-3 py-2">
        <div className="flex-1 min-w-[220px]">
          <div className="text-xs font-semibold text-gray-800">{title}</div>
          <div className="text-[11px] text-gray-600">{text}</div>
          {req?.maker_comment && <div className="text-[11px] text-gray-500 mt-0.5">Maker: “{req.maker_comment}”</div>}
        </div>
        <DecisionButtons actions={state.actions} busy={busy} onAction={act} labels={{ start: "Amend client", withdraw: "Withdraw amendment" }} />
      </div>
      {state.previous && <div className="px-3 pb-2"><DecisionNote request={state.previous} /></div>}
      {req && count > 0 && (
        <div className="border-t border-amber-100 px-3 py-2 bg-white/60">
          <button type="button" onClick={() => setShowChanges((v) => !v)} className="text-[11px] text-brand-600 hover:underline mb-1.5">
            {showChanges ? "Hide" : "Show"} changes
          </button>
          {showChanges && <ChangeList diff={state.diff} />}
        </div>
      )}
    </div>
  );
}
