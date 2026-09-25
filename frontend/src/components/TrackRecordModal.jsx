import React, { useEffect, useState } from "react";
import { accountsApi } from "../api/endpoints";
import { Icon, Badge, Modal, Spinner, ErrorBanner } from "./ui";
import { fmt, fmtDate } from "../utils/constants";
import { toast } from "../store/toast";

export default function TrackRecordModal({ account, onClose }) {
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const load = async () => {
    try {
      setLoading(true); setError(null);
      setRecord(await accountsApi.trackRecord(account.id));
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load track record");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [account.id]);

  const downloadPdf = async () => {
    try {
      setDownloading(true);
      await accountsApi.downloadTrackRecordPdf(account.id, `track-record-${account.account_uid}.pdf`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to download PDF");
    } finally { setDownloading(false); }
  };

  return (
    <Modal title={`Track Record — ${account.company_name}`} onClose={onClose}>
      {loading ? <Spinner /> : error ? <ErrorBanner message={error} onRetry={load} /> : record && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {[
              ["Total Cases", record.total_cases],
              ["Active Cases", record.active_cases],
              ["Onboarding Invoiced", fmt(record.total_onboarding_invoiced)],
              ["Invoices Paid", fmt(record.ledger_invoices_paid)],
              ["Invoices Outstanding", fmt(record.ledger_invoices_outstanding)],
            ].map(([label, value]) => (
              <div key={label} className="bg-gray-50 rounded-lg p-2.5 text-center">
                <p className="text-[10px] text-gray-400 uppercase tracking-wide">{label}</p>
                <p className="text-sm font-bold text-gray-800 mt-0.5">{value}</p>
              </div>
            ))}
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Client Profile</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 bg-gray-50 rounded-lg p-3">
              <div><span className="text-gray-400">Account Type:</span> {record.account_type}</div>
              <div><span className="text-gray-400">Industry:</span> {record.industry || "—"}</div>
              <div><span className="text-gray-400">Country:</span> {record.country || "—"}</div>
              <div><span className="text-gray-400">Risk Rating:</span> {record.risk_rating || "—"}</div>
              <div><span className="text-gray-400">KYC Status:</span> {record.kyc_status}</div>
              <div><span className="text-gray-400">Client Since:</span> {fmtDate(record.client_since)}</div>
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Cases ({record.cases.length})</p>
            {record.cases.length === 0 ? (
              <p className="text-xs text-gray-400">No cases on file yet.</p>
            ) : (
              <div className="space-y-1.5">
                {record.cases.map((c) => (
                  <div key={c.case_uid} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-xs">
                    <div className="min-w-0">
                      <div className="font-medium text-gray-800">{c.company_name} <span className="text-gray-400">({c.case_uid})</span></div>
                      <div className="text-gray-400">{c.jurisdiction || "—"} · {c.service_type || "—"}</div>
                    </div>
                    <div className="flex gap-1 flex-shrink-0 ml-2">
                      <Badge text={c.stage} />
                      <Badge text={c.invoice_status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {record.parties.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Parties on File</p>
              <div className="space-y-1.5">
                {record.parties.map((p, i) => (
                  <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-xs">
                    <span className="text-gray-800">{p.full_name} <span className="text-gray-400">({p.party_role})</span></span>
                    {p.effective_ownership_percent != null && <span className="text-gray-500">{p.effective_ownership_percent}%</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Close</button>
            <button onClick={downloadPdf} disabled={downloading}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50 flex items-center gap-1.5"
              style={{ background: "#1a3a5c" }}>
              <Icon name="download" size={14} /> {downloading ? "Downloading..." : "Download PDF"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
