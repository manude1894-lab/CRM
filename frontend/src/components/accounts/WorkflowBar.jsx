import React, { useEffect, useState } from "react";
import { workflowApi } from "../../api/endpoints";
import { Modal, Field, Select, Textarea } from "../ui";
import { useMasters } from "../../hooks/useMasters";
import { toast } from "../../store/toast";
import { fmtDate } from "../../utils/constants";
import { formatTimestamp } from "../../utils/auditFormat";

const STATUS_STYLE = {
  New: "bg-gray-100 text-gray-700",
  WIP: "bg-blue-50 text-blue-700",
  "Awaiting Approval": "bg-amber-100 text-amber-800",
  Approved: "bg-emerald-50 text-emerald-700",
  Active: "bg-emerald-100 text-emerald-800",
  Inactive: "bg-gray-200 text-gray-600",
  "Marked for Exit": "bg-red-50 text-red-700",
  Exited: "bg-red-100 text-red-800",
};

// Actions that need a short reason typed by the user.
const NEEDS_REASON = { deactivate: "Why is the client being made inactive?", mark_exit: "Why is the client exiting?" };
const MAX_WORDS = 250;
export const wordCount = (t) => (t || "").trim().split(/\s+/).filter(Boolean).length;

/**
 * BRD §11/§12/§15 — the client's lifecycle status, the actions this user may take now (disabled ones
 * say why), and the review history. Status only changes through these buttons.
 * onChanged(state) runs after every successful action so the form can refresh / lock.
 */
export default function WorkflowBar({ accountId, refreshKey, onChanged }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState(null); // { action, label }
  const [text, setText] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [kycDeclared, setKycDeclared] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const reasons = useMasters("rejection_reason", []);

  const load = () => workflowApi.get(accountId).then(setState).catch(() => setState(null));
  useEffect(() => { if (accountId) load(); }, [accountId, refreshKey]);
  if (!accountId || !state) return null;

  const run = async (action) => {
    setBusy(true);
    try {
      let next;
      if (action === "submit") next = await workflowApi.submit(accountId, text, kycDeclared);
      else if (action === "approve") next = await workflowApi.approve(accountId, text);
      else if (action === "reject") next = await workflowApi.reject(accountId, reasonCode, text);
      else if (action === "withdraw") next = await workflowApi.withdraw(accountId);
      else next = await workflowApi.status(accountId, action, text);
      setState(next);
      setDialog(null); setText(""); setReasonCode(""); setKycDeclared(false);
      toast.success(next.stage ? `Client is now with ${next.stage === "Approver" ? "the Approver" : "Compliance"}` : `Client is now ${next.status}`);
      onChanged?.(next);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
    } finally { setBusy(false); }
  };

  const open = (a) => {
    // Simple actions run straight away; others ask for a comment / reason first.
    if (["activate", "reactivate", "cancel_exit", "withdraw"].includes(a.action)) return run(a.action);
    setText(""); setReasonCode(""); setKycDeclared(false); setDialog(a);
  };

  const rejectTooShort = dialog?.action === "reject" && (text.trim().length < 15 || !reasonCode);
  const reasonMissing = NEEDS_REASON[dialog?.action] && !text.trim();
  // Triam mark-up §7/§10: mandatory comment boxes of up to 250 words.
  const commentLabel = dialog?.action === "submit" ? "RM/Sales comments"
    : dialog?.action === "approve" ? (state.stage === "Approver" ? "Approver's comments" : "Compliance comments") : null;
  const words = wordCount(text);
  const commentBad = !!commentLabel && (!text.trim() || words > MAX_WORDS);
  const kycMissing = dialog?.action === "submit" && !kycDeclared;

  return (
    <div className="mb-3 rounded-lg border border-gray-100 bg-white">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${STATUS_STYLE[state.status] || "bg-gray-100 text-gray-700"}`}>{state.status}</span>
        {state.stage && (
          <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-100">
            {state.stage === "Approver" ? "Step 2 of 2 · with the Approver" : "Step 1 of 2 · with Compliance (MLRO)"}
          </span>
        )}
        {state.status_updated_at && (
          <span className="text-[11px] text-gray-400">since {fmtDate(state.status_updated_at)}{state.status_updated_by ? ` · ${state.status_updated_by}` : ""}</span>
        )}
        <div className="flex flex-wrap gap-1.5 ml-auto">
          {state.actions.map((a) => (
            <button key={a.action} type="button" disabled={!a.allowed || busy} title={a.reason || ""} onClick={() => open(a)}
              className={`px-2.5 py-1 text-xs rounded-lg border disabled:opacity-40 disabled:cursor-not-allowed ${
                a.action === "reject" || a.action === "confirm_exit" || a.action === "mark_exit" ? "border-red-200 text-red-600 hover:bg-red-50"
                  : a.action === "approve" || a.action === "submit" || a.action === "activate" ? "border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                  : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              {a.label}
            </button>
          ))}
        </div>
      </div>
      {/* Why an action is unavailable (missing mandatory fields are listed by the checklist instead). */}
      {state.actions.some((a) => !a.allowed && a.reason && a.action !== "submit") && (
        <div className="px-3 pb-2 text-[11px] text-gray-500">
          {state.actions.filter((a) => !a.allowed && a.reason && a.action !== "submit").map((a) => <div key={a.action}>{a.label}: {a.reason}</div>)}
        </div>
      )}
      {state.locked && state.status === "Awaiting Approval" && (
        <div className="px-3 py-1.5 text-[11px] bg-amber-50 text-amber-800 border-t border-amber-100">
          Locked for review — editing is disabled until {state.stage === "Approver" ? "the Approver decides" : "Compliance decides or the submission is withdrawn"}.{state.stage !== "Approver" && " Compliance completes the CDD section meanwhile."}
        </div>
      )}
      {state.history.length > 0 && (
        <div className="border-t border-gray-100 px-3 py-1.5">
          <button type="button" onClick={() => setShowHistory((h) => !h)} className="text-[11px] text-brand-600 hover:underline">
            {showHistory ? "Hide" : "Show"} review history ({state.history.length})
          </button>
          {showHistory && (
            <div className="mt-1.5 space-y-1.5">
              {state.history.map((h) => (
                <div key={h.id} className="text-[11px] text-gray-600">
                  <span className="font-semibold">{h.status}</span> · submitted by {h.maker_name || "—"} {formatTimestamp(h.submitted_at)}
                  {h.decided_at && <> · {h.status.toLowerCase()} {h.checker_name ? `by ${h.checker_name} ` : ""}{formatTimestamp(h.decided_at)}</>}
                  {h.reason_code && <div className="text-red-600">Reason: {reasons.labelOf(h.reason_code)} — {h.reason_text}</div>}
                  {h.maker_comment && <div className="text-gray-500">RM/Sales comments: {h.maker_comment}{h.kyc_declared ? " · KYC verification confirmed" : ""}</div>}
                  {h.compliance_comment && <div className="text-gray-500">Compliance ({h.compliance_checker_name || "—"}, {formatTimestamp(h.compliance_decided_at)}): {h.compliance_comment}</div>}
                  {!h.reason_code && h.reason_text && <div className="text-gray-500">{h.request_type === "client_profile" && h.compliance_comment ? "Approver" : "Comment"}: {h.reason_text}</div>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {dialog && (
        <Modal title={dialog.label} onClose={() => setDialog(null)}>
          {dialog.action === "reject" && (
            <Field label="Reason" required>
              <Select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)}>
                <option value="">— choose —</option>
                {reasons.items.map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
              </Select>
            </Field>
          )}
          <Field label={dialog.action === "reject" ? "What needs fixing? (at least 15 characters)" : commentLabel || NEEDS_REASON[dialog.action] || "Comment (optional)"}
            required={dialog.action === "reject" || !!NEEDS_REASON[dialog.action] || !!commentLabel}>
            <Textarea rows={commentLabel ? 5 : 3} value={text} onChange={(e) => setText(e.target.value)} maxLength={commentLabel ? 4000 : dialog.action === "reject" ? 2000 : 500} />
            {commentLabel && <div className={`text-[11px] text-right mt-0.5 ${words > MAX_WORDS ? "text-red-600" : "text-gray-400"}`}>{words} / {MAX_WORDS} words</div>}
          </Field>
          {dialog.action === "submit" && (
            <>
              <label className="flex items-start gap-2 text-xs text-gray-700 mb-3">
                <input type="checkbox" className="mt-0.5" checked={kycDeclared} onChange={(e) => setKycDeclared(e.target.checked)} />
                <span>I confirm that the client's KYC verification is done as per the extant verification procedures.</span>
              </label>
              <p className="text-xs text-gray-500 mb-3">Goes to Compliance, then to the Approver.</p>
            </>
          )}
          {dialog.action === "approve" && (
            <p className="text-xs text-gray-500 -mt-2 mb-3">
              {state.stage === "Approver" ? "You give the final approval; the client becomes Approved and available for service requests."
                : "You confirm the CDD section is complete and the information and documents are reviewed. The Client ID is issued and the client goes to the Approver."}
            </p>
          )}
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setDialog(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={() => run(dialog.action)} disabled={busy || rejectTooShort || reasonMissing || commentBad || kycMissing}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50" style={{ background: "#1a3a5c" }}>
              {busy ? "Working…" : dialog.label}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
