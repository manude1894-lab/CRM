import React, { useState } from "react";
import { Modal, Field, Select, Textarea } from "../ui";
import { useMasters } from "../../hooks/useMasters";
import { fmtDate } from "../../utils/constants";

export const REQUEST_TYPE_LABEL = {
  client_profile: "New Client",
  client_amendment: "Client Amendment",
  case_creation: "New Case",
  case_amendment: "Case Amendment",
};

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const show = (v) => (v === null || v === undefined || v === "" ? "—" : ISO_DATE.test(String(v)) ? fmtDate(v) : String(v));

/** Before / after table for an amendment (client fields, parties, or case fields). */
export function ChangeList({ diff }) {
  if (!diff) return null;
  const fields = diff.account || diff.case || [];
  const parties = diff.parties || [];
  if (!fields.length && !parties.length) return <p className="text-xs text-gray-400">No changes yet.</p>;
  return (
    <div className="space-y-3">
      {fields.length > 0 && (
        <table className="w-full text-xs border border-gray-100 rounded">
          <thead>
            <tr className="bg-gray-50 text-gray-500">
              <th className="text-left px-2 py-1.5 font-semibold w-1/3">Field</th>
              <th className="text-left px-2 py-1.5 font-semibold">Current</th>
              <th className="text-left px-2 py-1.5 font-semibold">Proposed</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((c) => (
              <tr key={c.field} className="border-t border-gray-100 align-top">
                <td className="px-2 py-1.5 text-gray-700 font-medium">{c.label}</td>
                <td className="px-2 py-1.5 text-gray-500 line-through decoration-gray-300">{show(c.old)}</td>
                <td className="px-2 py-1.5 text-emerald-800 bg-emerald-50/60">{show(c.new)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {parties.map((p, i) => (
        <div key={i} className="border border-gray-100 rounded px-2 py-1.5 text-xs">
          <div className="font-medium text-gray-700">
            <span className={`mr-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
              p.action === "added" ? "bg-emerald-100 text-emerald-800" : p.action === "removed" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"}`}>
              {p.action}
            </span>
            {p.role}: {p.name || "—"}
          </div>
          {p.changes.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-gray-600">
              {p.changes.map((c) => (
                <li key={c.field}>{c.label}: {p.action === "changed" && <><span className="line-through text-gray-400">{show(c.old)}</span> → </>}<span className="text-emerald-800">{show(c.new)}</span></li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

/** A previous Compliance decision the maker needs to see (e.g. why a change was rejected). */
export function DecisionNote({ request }) {
  const reasons = useMasters("rejection_reason", []);
  if (!request) return null;
  const rejected = request.status === "Rejected";
  return (
    <div className={`text-xs rounded px-2 py-1.5 ${rejected ? "bg-red-50 text-red-700" : "bg-gray-50 text-gray-600"}`}>
      {request.status === "Withdrawn" ? "Withdrawn from Compliance" : request.status}
      {request.checker_name ? ` by ${request.checker_name}` : ""}{request.decided_at ? ` on ${fmtDate(request.decided_at)}` : ""}
      {request.reason_code && <> — <strong>{reasons.labelOf(request.reason_code)}</strong>: {request.reason_text}</>}
    </div>
  );
}

/**
 * Buttons for a Compliance decision. `actions` lists what this user may do (from the API):
 * approve | reject | withdraw | submit | resubmit | discard. Reject asks for a reason from the
 * master list and an explanation of at least 15 characters (BRD §14).
 */
export function DecisionButtons({ actions, busy, onAction, labels = {} }) {
  const [dialog, setDialog] = useState(null);
  const [text, setText] = useState("");
  const [code, setCode] = useState("");
  const reasons = useMasters("rejection_reason", []);
  const LABEL = { approve: "Approve", reject: "Reject", withdraw: "Withdraw", submit: "Submit to Compliance", resubmit: "Resubmit to Compliance", discard: "Discard changes", ...labels };
  const asks = ["approve", "reject", "submit", "resubmit"];

  const click = (a) => {
    if (asks.includes(a)) { setText(""); setCode(""); setDialog(a); } else onAction(a, {});
  };
  const confirm = async () => {
    const body = dialog === "reject" ? { reason_code: code, reason_text: text } : { comment: text || null };
    const ok = await onAction(dialog, body);
    if (ok !== false) setDialog(null);
  };
  const rejectInvalid = dialog === "reject" && (!code || text.trim().length < 15);

  return (
    <>
      <div className="flex flex-wrap gap-1.5">
        {actions.map((a) => (
          <button key={a} type="button" disabled={busy} onClick={() => click(a)}
            className={`px-2.5 py-1 text-xs rounded-lg border disabled:opacity-40 ${
              a === "reject" || a === "discard" ? "border-red-200 text-red-600 hover:bg-red-50"
                : a === "approve" || a === "submit" || a === "resubmit" ? "border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
            {LABEL[a] || a}
          </button>
        ))}
      </div>
      {dialog && (
        <Modal title={LABEL[dialog]} onClose={() => setDialog(null)}>
          {dialog === "reject" && (
            <Field label="Reason" required>
              <Select value={code} onChange={(e) => setCode(e.target.value)}>
                <option value="">— choose —</option>
                {reasons.items.map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
              </Select>
            </Field>
          )}
          <Field label={dialog === "reject" ? "What needs fixing? (at least 15 characters)" : "Comment (optional)"} required={dialog === "reject"}>
            <Textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} maxLength={dialog === "reject" ? 2000 : 1000} />
          </Field>
          {dialog === "approve" && <p className="text-xs text-gray-500 -mt-2 mb-3">The change takes effect as soon as you approve it.</p>}
          {(dialog === "submit" || dialog === "resubmit") && <p className="text-xs text-gray-500 -mt-2 mb-3">It will be locked until Compliance decides.</p>}
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setDialog(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={confirm} disabled={busy || rejectInvalid}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50" style={{ background: "#1a3a5c" }}>
              {busy ? "Working…" : LABEL[dialog]}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
