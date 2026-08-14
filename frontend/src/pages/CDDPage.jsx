import React, { useEffect, useState } from "react";
import { casesApi, cddApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Spinner, ErrorBanner } from "../components/ui";
import { DOCUMENT_STATUS_OPTIONS, AML_RISK_OPTIONS } from "../utils/constants";

const SCREENING_STATUSES = ["Submitted", "Under Review"];

export default function CDDPage() {
  const canReview = useAuthStore((s) => ["admin", "screening"].includes(s.user?.role));
  const [cases, setCases] = useState([]);
  const [cddByCase, setCddByCase] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [reviewModal, setReviewModal] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [newDocType, setNewDocType] = useState("");

  const load = async () => {
    try {
      setLoading(true); setError(null);
      const [res, cddList] = await Promise.all([
        casesApi.list({ limit: 500 }),
        cddApi.listAll(),
      ]);
      const allCases = res.items || [];
      const map = {};
      (cddList || []).forEach((cdd) => { map[cdd.case_id] = cdd; });
      setCases(allCases);
      setCddByCase(map);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to load CDD queue");
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const queue = cases.filter((c) => {
    const cdd = cddByCase[c.id];
    if (!cdd) return false;
    const cddInProgress = SCREENING_STATUSES.includes(cdd.cdd_form_status) || SCREENING_STATUSES.includes(cdd.kyc_verification_status);
    const stageInCDD = c.stage === "CDD/KYC In Review" || c.stage === "CDD Approved";
    return cddInProgress || stageInCDD;
  });

  const updateStatus = async (caseId, field, value) => {
    try {
      await cddApi.update(caseId, { [field]: value });
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Update failed");
    }
  };

  const addDocument = async (caseId) => {
    if (!newDocType.trim()) return;
    try {
      await cddApi.addDocument(caseId, { doc_type: newDocType.trim(), received: false });
      setNewDocType("");
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to add document");
    }
  };

  const toggleReceived = async (doc) => {
    try {
      await cddApi.updateDocument(doc.id, { received: !doc.received, received_date: !doc.received ? new Date().toISOString().split("T")[0] : null });
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Update failed");
    }
  };

  const submitReview = async (approve) => {
    try {
      await cddApi.review(selected.id, { approve, rejection_reason: approve ? null : rejectionReason });
      setReviewModal(false); setRejectionReason(""); setSelected(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Review failed");
    }
  };

  if (loading) return <Spinner />;
  if (error) return <ErrorBanner message={error} onRetry={load} />;

  const selectedCdd = selected ? cddByCase[selected.id] : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">CDD / KYC Screening</h1>
        <p className="text-sm text-gray-500">{queue.length} cases awaiting screening review</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-2">
          {queue.length === 0 && <p className="text-sm text-gray-400 text-center py-8">No cases awaiting screening.</p>}
          {queue.map((c) => {
            const cdd = cddByCase[c.id];
            return (
              <button key={c.id} onClick={() => setSelected(c)}
                className={`w-full text-left bg-white border rounded-xl p-4 shadow-sm hover:shadow-md transition-all ${selected?.id === c.id ? "border-blue-400 ring-1 ring-blue-200" : "border-gray-100"}`}>
                <div className="font-semibold text-sm text-gray-800">{c.company_name}</div>
                <div className="text-xs text-gray-400 mb-2">{c.case_uid}</div>
                <div className="flex gap-1 flex-wrap">
                  <Badge text={cdd.cdd_form_status} />
                  <Badge text={cdd.kyc_verification_status} />
                </div>
              </button>
            );
          })}
        </div>

        <div className="lg:col-span-2">
          {!selected ? (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">Select a case to view its CDD/KYC checklist.</div>
          ) : (
            <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div>
                  <h3 className="text-base font-bold text-gray-800">{selected.company_name}</h3>
                  <p className="text-xs text-gray-400">{selected.case_uid}</p>
                </div>
                {canReview && (
                  <button onClick={() => setReviewModal(true)}
                    className="px-3 py-1.5 text-xs text-white rounded-lg" style={{ background: "#2B6D9A" }}>
                    Review CDD/KYC
                  </button>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Field label="CDD Form Status">
                  <Select value={selectedCdd?.cdd_form_status || "Not Started"}
                    disabled={!canReview}
                    onChange={(e) => updateStatus(selected.id, "cdd_form_status", e.target.value)}>
                    {DOCUMENT_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
                  </Select>
                </Field>
                <Field label="KYC Verification Status">
                  <Select value={selectedCdd?.kyc_verification_status || "Not Started"}
                    disabled={!canReview}
                    onChange={(e) => updateStatus(selected.id, "kyc_verification_status", e.target.value)}>
                    {DOCUMENT_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
                  </Select>
                </Field>
                <Field label="AML Risk Rating">
                  <Select value={selectedCdd?.aml_risk_rating || ""}
                    disabled={!canReview}
                    onChange={(e) => updateStatus(selected.id, "aml_risk_rating", e.target.value || null)}>
                    <option value="">— Not Assessed —</option>
                    {AML_RISK_OPTIONS.map((r) => <option key={r}>{r}</option>)}
                  </Select>
                </Field>
              </div>

              {selectedCdd?.rejection_reason && (
                <div className="bg-red-50 border border-red-100 rounded-lg p-3 text-xs text-red-700">
                  <strong>Rejection reason:</strong> {selectedCdd.rejection_reason}
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-gray-600 mb-2">Document Checklist</p>
                <div className="space-y-1.5">
                  {(selectedCdd?.documents || []).map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-2">
                        <button onClick={() => toggleReceived(doc)}
                          className={`w-5 h-5 rounded border flex items-center justify-center ${doc.received ? "bg-emerald-500 border-emerald-500 text-white" : "border-gray-300"}`}>
                          {doc.received && <Icon name="check" size={12} />}
                        </button>
                        <span className="text-xs text-gray-700">{doc.doc_type}</span>
                      </div>
                      <span className="text-xs text-gray-400">{doc.received_date || "Pending"}</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 mt-2">
                  <Input placeholder="Add document type..." value={newDocType} onChange={(e) => setNewDocType(e.target.value)} />
                  <button onClick={() => addDocument(selected.id)} className="px-3 py-2 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">Add</button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {reviewModal && (
        <Modal title="Review CDD / KYC" onClose={() => setReviewModal(false)}>
          <p className="text-sm text-gray-600 mb-4">Approve clears both CDD form and KYC verification. Reject requires a reason and marks the case Rejected.</p>
          <Field label="Rejection Reason (required if rejecting)">
            <Input value={rejectionReason} onChange={(e) => setRejectionReason(e.target.value)} />
          </Field>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => submitReview(false)} className="px-4 py-2 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50">Reject</button>
            <button onClick={() => submitReview(true)} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#10b981" }}>Approve</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
