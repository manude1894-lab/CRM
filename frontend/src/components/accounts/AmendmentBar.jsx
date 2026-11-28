import React, { useEffect, useState } from "react";
import { amendmentApi } from "../../api/endpoints";
import { toast } from "../../store/toast";
import { formatTimestamp } from "../../utils/auditFormat";
import { ChangeList, DecisionButtons, DecisionNote } from "../compliance/ComplianceParts";
import { Icon } from "../ui";
import ClientDocumentsFolder from "./ClientDocumentsFolder";

/**
 * BRD §13 — existing-client maintenance. On an approved client the profile changes only through an
 * amendment: "Amend client" opens a draft, section saves go into the draft, and the maker submits it
 * to Compliance. The live record changes when a CO / MLRO approves.
 * onState(state) reports the current amendment so the form can show the staged values and decide
 * whether it is editable.
 */
export default function AmendmentBar({ accountId, refreshKey, onState, onDecided, submitSignal = 0 }) {
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
        start: "Amendment started. Your changes stay in draft until Compliance approves them.",
        submit: "Amendment sent to Compliance for approval.", approve: "Amendment approved and applied.",
        reject: "Amendment rejected and returned to the maker.", withdraw: "Amendment withdrawn and returned to draft.",
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

  // Triam UAT 27-11-2026: on an approved client the way to change data stands out as soon as Edit profile opens.
  if (!req && state.actions.includes("start")) {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-3 rounded-xl border-2 border-brand-200 bg-brand-50 px-4 py-3">
        <div className="flex-1 min-w-[220px]">
          <div className="text-sm font-semibold text-brand-800">This client is approved</div>
          <div className="text-xs text-gray-600">To change its data, amend it. The changes, with any supporting documents, go to Compliance for approval.</div>
        </div>
        <button type="button" disabled={busy} onClick={() => act("start")}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 disabled:opacity-60">
          <Icon name="edit" size={15} /> {busy ? "Starting…" : "Amend client data"}
        </button>
      </div>
    );
  }
  let tone = "border-blue-100 bg-blue-50/60", title, text;
  if (!req) {
    title = "Approved client";
    text = "Changes to an approved client go to Compliance for approval.";
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
        <DecisionButtons actions={state.actions} busy={busy} onAction={act} labels={{ start: "Amend client", withdraw: "Withdraw amendment" }} submitSignal={submitSignal} />
      </div>
      {state.previous && <div className="px-3 pb-2"><DecisionNote request={state.previous} /></div>}
      {/* Triam UAT 27-11-2026: documents supporting the change (e.g. the new LEI certificate), seen by Compliance. */}
      {req && (mineDraft || (state.documents || []).length > 0) && (
        <div className="border-t border-amber-100 px-3 py-2 bg-white/60">
          <div className="text-[11px] font-semibold text-gray-700 mb-1.5">Supporting documents</div>
          <ClientDocumentsFolder accountId={accountId} amendmentId={req.id} viewOnly={!mineDraft} uploadLabel="Add supporting document"
            emptyText="None yet. Add the document that supports the change, e.g. the new certificate." onChange={() => amendmentApi.get(accountId).then(apply)} />
        </div>
      )}
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
