import React, { useEffect, useState } from "react";
import { casesApi, cddApi, directorsApi, shareholdersApi, ubosApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Spinner, ErrorBanner } from "../components/ui";
import AMLAssessmentPanel from "../components/AMLAssessmentPanel";
import PEPAssessmentPanel from "../components/PEPAssessmentPanel";
import DocumentsPanel from "../components/DocumentsPanel";
import { DOCUMENT_STATUS_OPTIONS, AML_RISK_OPTIONS } from "../utils/constants";

const directorName = (d) => d.director_type === "Corporate"
  ? (d.corporate_name || "Corporate Director")
  : [d.first_name, d.middle_name, d.last_name].filter(Boolean).join(" ") || "Individual Director";

const SCREENING_STATUSES = ["Submitted", "Under Review"];

const expiryInfo = (dateStr) => {
  if (!dateStr) return null;
  const days = Math.floor((new Date(dateStr).getTime() - Date.now()) / 86400000);
  if (days < 0) return { cls: "text-red-600 border-red-300", label: "expired" };
  if (days <= 60) return { cls: "text-amber-600 border-amber-300", label: `${days}d` };
  return { cls: "text-gray-500 border-gray-200", label: null };
};

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
  const [directors, setDirectors] = useState([]);
  const [shareholders, setShareholders] = useState([]);
  const [ubos, setUbos] = useState([]);
  const [openAttach, setOpenAttach] = useState(null);

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

  useEffect(() => {
    if (!selected) { setDirectors([]); setShareholders([]); setUbos([]); return; }
    Promise.all([directorsApi.list(selected.id), shareholdersApi.list(selected.id), ubosApi.list(selected.id)])
      .then(([ds, ss, us]) => { setDirectors(ds || []); setShareholders(ss || []); setUbos(us || []); })
      .catch(() => { setDirectors([]); setShareholders([]); setUbos([]); });
  }, [selected?.id]);

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

  const setExpiry = async (doc, value) => {
    try {
      await cddApi.updateDocument(doc.id, { expiry_date: value || null });
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
                {(() => {
                  const allDocs = selectedCdd?.documents || [];
                  const companyDocs = allDocs.filter((d) => !d.director_id && !d.shareholder_id && !d.ubo_id);
                  const uboName = (u) => [u.first_name, u.middle_name, u.last_name].filter(Boolean).join(" ") || "UBO";
                  const groups = [
                    { key: "company", label: "Company", docs: companyDocs, note: null },
                    ...directors.map((d) => ({
                      key: `d${d.id}`,
                      label: `Director — ${directorName(d)}`,
                      docs: allDocs.filter((doc) => doc.director_id === d.id),
                      note: null,
                    })),
                    ...shareholders.map((s) => ({
                      key: `s${s.id}`,
                      label: `Shareholder — ${s.name}${s.shareholding_percent != null ? ` (${s.shareholding_percent}%)` : ""}`,
                      docs: allDocs.filter((doc) => doc.shareholder_id === s.id),
                      note: s.shareholding_percent != null && s.shareholding_percent < 10
                        ? "CDD optional — below 10% interest threshold"
                        : null,
                    })),
                    ...ubos.map((u) => ({
                      key: `u${u.id}`,
                      label: `UBO — ${uboName(u)}${u.percentage_interest != null ? ` (${u.percentage_interest}%)` : ""}`,
                      docs: allDocs.filter((doc) => doc.ubo_id === u.id),
                      note: u.percentage_interest != null && u.percentage_interest < 10
                        ? "CDD optional — below 10% interest threshold"
                        : null,
                    })),
                  ];
                  return (
                    <div className="space-y-4">
                      {groups.map((g) => (
                        <div key={g.key}>
                          <p className="text-xs font-medium text-gray-500 mb-1.5">{g.label}</p>
                          {g.docs.length === 0 ? (
                            <p className="text-xs text-gray-400 italic pl-1">{g.note || "No documents required."}</p>
                          ) : (
                            <div className="space-y-1.5">
                              {g.docs.map((doc) => (
                                <div key={doc.id} className="bg-gray-50 rounded-lg">
                                  <div className="flex items-center justify-between p-2">
                                    <div className="flex items-center gap-2">
                                      <button onClick={() => toggleReceived(doc)}
                                        className={`w-5 h-5 rounded border flex items-center justify-center flex-shrink-0 ${doc.received ? "bg-emerald-500 border-emerald-500 text-white" : "border-gray-300"}`}>
                                        {doc.received && <Icon name="check" size={12} />}
                                      </button>
                                      <span className="text-xs text-gray-700">{doc.doc_type}</span>
                                    </div>
                                    <div className="flex items-center gap-2 ml-2">
                                      {(() => {
                                        const ei = expiryInfo(doc.expiry_date);
                                        return (
                                          <label className="flex items-center gap-1 text-[11px] text-gray-400" title="Document expiry (e.g. passport)">
                                            <span>exp</span>
                                            <input type="date" value={doc.expiry_date || ""}
                                              onChange={(e) => setExpiry(doc, e.target.value)}
                                              className={`border rounded px-1 py-0.5 text-[11px] focus:outline-none ${ei ? ei.cls : "text-gray-500 border-gray-200"}`} />
                                            {ei?.label && <span className={`font-medium ${ei.cls.split(" ")[0]}`}>{ei.label}</span>}
                                          </label>
                                        );
                                      })()}
                                      <button onClick={() => setOpenAttach(openAttach === doc.id ? null : doc.id)}
                                        className={`flex items-center gap-1 text-xs ${(doc.attachments?.length || 0) > 0 ? "text-blue-600" : "text-gray-400"} hover:text-blue-600`}>
                                        <Icon name="download" size={12} /> {doc.attachments?.length || 0}
                                      </button>
                                      <span className="text-xs text-gray-400 whitespace-nowrap">{doc.received_date || "Pending"}</span>
                                    </div>
                                  </div>
                                  {openAttach === doc.id && (
                                    <div className="px-2 pb-2">
                                      <DocumentsPanel caseId={selected.id} scope={{ case_document_id: doc.id }} compact onChange={load} />
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}
                <div className="flex gap-2 mt-3">
                  <Input placeholder="Add company-level document..." value={newDocType} onChange={(e) => setNewDocType(e.target.value)} />
                  <button onClick={() => addDocument(selected.id)} className="px-3 py-2 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">Add</button>
                </div>
              </div>

              {(() => {
                const parties = [
                  ...directors.map((d) => ({ id: d.id, _kind: "Director", _label: directorName(d) })),
                  ...shareholders.map((s) => ({ id: s.id, _kind: "Shareholder", _label: s.name })),
                  ...ubos.map((u) => ({ id: u.id, _kind: "UBO", _label: [u.first_name, u.middle_name, u.last_name].filter(Boolean).join(" ") || "UBO" })),
                ];
                return (
                  <>
                    <AMLAssessmentPanel caseId={selected.id} entityName={selected.company_name} parties={parties} />
                    <PEPAssessmentPanel caseId={selected.id} parties={parties} />
                  </>
                );
              })()}

              <div className="border-t border-gray-100 pt-4">
                <p className="text-xs font-semibold text-gray-600 mb-2">Case Documents <span className="text-gray-400 font-normal">· not tied to a checklist item</span></p>
                <DocumentsPanel caseId={selected.id} scope={null} onChange={load} />
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
