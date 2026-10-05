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
  const [showHistory, setShowHistory] = useState(false);
  const reasons = useMasters("rejection_reason", []);

  const load = () => workflowApi.get(accountId).then(setState).catch(() => setState(null));
  useEffect(() => { if (accountId) load(); }, [accountId, refreshKey]);
  if (!accountId || !state) return null;

  const run = async (action) => {
    setBusy(true);
    try {
      let next;
      if (action === "submit") next = await workflowApi.submit(accountId, text);
      else if (action === "approve") next = await workflowApi.approve(accountId, text);
      else if (action === "reject") next = await workflowApi.reject(accountId, reasonCode, text);
      else if (action === "withdraw") next = await workflowApi.withdraw(accountId);
      else next = await workflowApi.status(accountId, action, text);
      setState(next);
      setDialog(null); setText(""); setReasonCode("");
      toast.success(`Client is now ${next.status}`);
      onChanged?.(next);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
    } finally { setBusy(false); }
  };

  const open = (a) => {
    // Simple actions run straight away; others ask for a comment / reason first.
    if (["activate", "reactivate", "cancel_exit", "withdraw"].includes(a.action)) return run(a.action);
    setText(""); setReasonCode(""); setDialog(a);
  };

  const rejectTooShort = dialog?.action === "reject" && (text.trim().length < 15 || !reasonCode);
  const reasonMissing = NEEDS_REASON[dialog?.action] && !text.trim();

  return (
    <div className="mb-3 rounded-lg border border-gray-100 bg-white">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${STATUS_STYLE[state.status] || "bg-gray-100 text-gray-700"}`}>{state.status}</span>
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
      {state.actions.some((a) => !a.allowed && a.reason) && (
        <div className="px-3 pb-2 text-[11px] text-gray-500">
          {state.actions.filter((a) => !a.allowed && a.reason).map((a) => <div key={a.action}>{a.label}: {a.reason}</div>)}
        </div>
      )}
      {state.locked && state.status === "Awaiting Approval" && (
        <div className="px-3 py-1.5 text-[11px] bg-amber-50 text-amber-800 border-t border-amber-100">
          Locked for review — editing is disabled until the checker decides or the submission is withdrawn.
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
                  {!h.reason_code && h.reason_text && <div className="text-gray-500">Comment: {h.reason_text}</div>}
                  {h.maker_comment && <div className="text-gray-500">Maker: {h.maker_comment}</div>}
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
          <Field label={dialog.action === "reject" ? "What needs fixing? (at least 15 characters)" : NEEDS_REASON[dialog.action] || "Comment (optional)"}
            required={dialog.action === "reject" || !!NEEDS_REASON[dialog.action]}>
            <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} maxLength={dialog.action === "reject" ? 2000 : 500} />
          </Field>
          {dialog.action === "submit" && <p className="text-xs text-gray-500 -mt-2 mb-3">The profile will be locked until an approver decides.</p>}
          {dialog.action === "approve" && <p className="text-xs text-gray-500 -mt-2 mb-3">You confirm you've reviewed the information and documents.</p>}
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setDialog(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={() => run(dialog.action)} disabled={busy || rejectTooShort || reasonMissing}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50" style={{ background: "#1a3a5c" }}>
              {busy ? "Working…" : dialog.label}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
