import React, { useEffect, useState } from "react";
import { amendmentApi, caseComplianceApi, casesApi, workflowApi } from "../api/endpoints";
import { Modal, Spinner, ErrorBanner, PageHeader } from "../components/ui";
import { useMasters } from "../hooks/useMasters";
import { formatTimestamp } from "../utils/auditFormat";
import { fmtDate } from "../utils/constants";
import { toast } from "../store/toast";
import { ChangeList, DecisionButtons, REQUEST_TYPE_LABEL } from "../components/compliance/ComplianceParts";

const TABS = ["Pending", "Approved", "Rejected", "Withdrawn"];
const TYPES = [["", "All"], ["client_profile", "New Clients"], ["client_amendment", "Client Amendments"],
  ["case_creation", "New Cases"], ["case_amendment", "Case Amendments"]];
const TYPE_STYLE = {
  client_profile: "bg-blue-50 text-blue-700", client_amendment: "bg-amber-50 text-amber-800",
  case_creation: "bg-violet-50 text-violet-700", case_amendment: "bg-orange-50 text-orange-700",
};

// Case fields shown to the checker when a new case is reviewed.
const CASE_FIELDS = [
  ["case_uid", "Case"], ["company_name", "Company Name"], ["service_type", "Service"], ["jurisdiction", "Jurisdiction"],
  ["source", "Source"], ["introducer", "Introducer"], ["onboarding_date", "Onboarding Date"], ["stage", "Stage"], ["notes", "Notes"],
];

/**
 * The Compliance review desk: every new client, client amendment, new case and case change waiting
 * for a CO / MLRO decision (BRD §12, §13, §15). A checker can never approve their own submission.
 */
export default function ApprovalsPage({ onNavigate }) {
  const [tab, setTab] = useState("Pending");
  const [type, setType] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [review, setReview] = useState(null); // the row being reviewed in a modal
  const reasons = useMasters("rejection_reason", []);

  const load = async () => {
    setLoading(true); setError(null);
    try { setRows(await workflowApi.inbox(tab, type)); }
    catch (e) { setError(e.response?.data?.detail || "Failed to load the Compliance inbox"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [tab, type]);

  const open = (r) => {
    // New client profiles are reviewed on the client screen itself, next to the information.
    if (r.request_type === "client_profile") onNavigate?.({ page: "accounts", accountId: r.account_id, openForm: true });
    else setReview(r);
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Compliance"
        subtitle={<>New clients, changes to approved clients, new cases and changes to cases waiting for Compliance approval.
          You can't approve anything you submitted yourself.</>} />
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm -mb-px border-b-2 ${tab === t ? "border-brand-500 text-brand-700 font-medium" : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {t}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {TYPES.map(([code, label]) => (
          <button key={code || "all"} onClick={() => setType(code)}
            className={`px-3 py-1 text-xs rounded-full border ${type === code ? "border-brand-500 bg-brand-50 text-brand-700 font-medium" : "border-gray-200 text-gray-500 hover:bg-gray-50"}`}>
            {label}
          </button>
        ))}
      </div>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-xs text-gray-500">
                <th className="text-left py-2.5 px-4 font-semibold">Type</th>
                <th className="text-left py-2.5 px-4 font-semibold">Client / Case</th>
                <th className="text-left py-2.5 px-4 font-semibold">Submitted by</th>
                <th className="text-left py-2.5 px-4 font-semibold">Submitted</th>
                {tab !== "Pending" && <th className="text-left py-2.5 px-4 font-semibold">Decision</th>}
                <th className="py-2.5 px-4" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-gray-50 align-top">
                  <td className="py-2.5 px-4">
                    <span className={`text-[11px] font-semibold px-2 py-0.5 rounded ${TYPE_STYLE[r.request_type] || "bg-gray-100 text-gray-600"}`}>
                      {REQUEST_TYPE_LABEL[r.request_type] || r.request_type}
                    </span>
                    {r.changes?.count > 0 && <div className="text-[11px] text-gray-400 mt-1">{r.changes.count} change{r.changes.count === 1 ? "" : "s"}</div>}
                    {r.request_type === "client_profile" && r.status === "Pending" && (
                      <div className="text-[11px] text-amber-700 mt-1">{r.stage === "Approver" ? "With the Approver" : "With Compliance"}</div>
                    )}
                  </td>
                  <td className="py-2.5 px-4">
                    <div className="font-medium text-gray-800">{r.case_name || r.company_name}</div>
                    <div className="text-xs text-gray-400">
                      <span className="font-mono">{r.case_uid || r.client_id || r.temp_id || "—"}</span>
                      {r.case_uid && r.client_id && <> · client <span className="font-mono">{r.client_id}</span></>}
                      {!r.case_uid && r.account_type && <> · {r.account_type}</>}
                    </div>
                    {r.maker_comment && <div className="text-xs text-gray-500 mt-0.5">“{r.maker_comment}”</div>}
                  </td>
                  <td className="py-2.5 px-4 text-xs text-gray-600">{r.maker_name || "—"}</td>
                  <td className="py-2.5 px-4 text-xs text-gray-600">{formatTimestamp(r.submitted_at)}</td>
                  {tab !== "Pending" && (
                    <td className="py-2.5 px-4 text-xs text-gray-600">
                      {r.checker_name || "—"} · {formatTimestamp(r.decided_at)}
                      {r.reason_code && <div className="text-red-600">{reasons.labelOf(r.reason_code)} — {r.reason_text}</div>}
                    </td>
                  )}
                  <td className="py-2.5 px-4 text-right">
                    <button onClick={() => open(r)} className="px-3 py-1.5 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>
                      {tab === "Pending" ? "Review" : "Open"}
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={6} className="py-10 text-center text-sm text-gray-400">{tab === "Pending" ? "Nothing waiting for Compliance." : `No ${tab.toLowerCase()} requests.`}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      {review && (
        <ReviewModal row={review} onNavigate={onNavigate} onClose={() => setReview(null)} onDecided={() => { setReview(null); load(); }} />
      )}
    </div>
  );
}

/** Review of a client amendment, a new case or a case amendment, with the decision buttons. */
function ReviewModal({ row, onClose, onDecided, onNavigate }) {
  const isCase = row.request_type.startsWith("case_");
  const [state, setState] = useState(null);
  const [caseInfo, setCaseInfo] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (isCase) {
      caseComplianceApi.get(row.case_id).then(setState).catch(() => setState({ actions: [] }));
      casesApi.get(row.case_id).then(setCaseInfo).catch(() => {});
    } else {
      amendmentApi.get(row.account_id).then(setState).catch(() => setState({ actions: [] }));
    }
  }, [row.id]);

  // The pending request is the one being reviewed; past requests in the inbox are read-only.
  const isCurrent = row.status === "Pending" && state?.request?.id === row.id;
  const actions = isCurrent ? (state?.actions || []).filter((a) => ["approve", "reject"].includes(a)) : [];
  const diff = row.changes || (isCurrent ? state?.diff : null);

  const act = async (action, body) => {
    setBusy(true);
    try {
      if (isCase) await caseComplianceApi.act(row.case_id, action, body);
      else await amendmentApi.act(row.account_id, action, body);
      toast.success({ approve: "Approved", reject: "Rejected and returned to the maker", withdraw: "Withdrawn" }[action] || "Done");
      onDecided();
      return true;
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
      return false;
    } finally { setBusy(false); }
  };

  const goto = () => {
    onClose();
    if (isCase) onNavigate?.({ page: "cases", caseId: row.case_id });
    else onNavigate?.({ page: "accounts", accountId: row.account_id, openForm: true });
  };

  return (
    <Modal title={`${REQUEST_TYPE_LABEL[row.request_type]} — ${row.case_name || row.company_name}`} onClose={onClose}>
      <div className="space-y-3">
        <div className="text-xs text-gray-500">
          Submitted by <strong className="text-gray-700">{row.maker_name || "—"}</strong> {formatTimestamp(row.submitted_at)}
          {row.maker_comment && <div className="mt-0.5">Maker's note: “{row.maker_comment}”</div>}
        </div>
        {!state ? <Spinner /> : (
          <>
            {row.request_type === "case_creation" && caseInfo && (
              <table className="w-full text-xs border border-gray-100 rounded">
                <tbody>
                  {CASE_FIELDS.map(([k, label]) => (
                    <tr key={k} className="border-t border-gray-100">
                      <td className="px-2 py-1.5 text-gray-500 w-1/3">{label}</td>
                      <td className="px-2 py-1.5 text-gray-800">{k.endsWith("_date") ? fmtDate(caseInfo[k]) : (caseInfo[k] || "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {diff && <ChangeList diff={diff} />}
            {row.status !== "Pending" && (
              <p className="text-xs text-gray-500">{row.status} by {row.checker_name || "—"} {formatTimestamp(row.decided_at)}{row.reason_text ? ` — ${row.reason_text}` : ""}</p>
            )}
          </>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-gray-100">
          <button onClick={goto} className="text-xs text-brand-600 hover:underline">Open the full {isCase ? "case" : "client"}</button>
          {actions.length > 0 && <DecisionButtons actions={actions} busy={busy} onAction={act} />}
          {isCurrent && actions.length === 0 && <span className="text-[11px] text-gray-400">You submitted this — another approver must review it.</span>}
        </div>
      </div>
    </Modal>
  );
}
