import React from "react";
import { Icon, Badge } from "../ui";
import { fmt, fmtDate } from "../../utils/constants";

const Stat = ({ label, value, small }) => (
  <div className="bg-gray-50 rounded-lg p-2">
    <p className="text-xs text-gray-500">{label}</p>
    <p className={small ? "text-xs font-bold text-gray-800 truncate" : "text-sm font-bold text-gray-800"}>{value}</p>
  </div>
);

const ActionButton = ({ icon, label, onClick, className = "mb-2" }) => (
  <button onClick={(e) => { e.stopPropagation(); onClick(); }}
    className={`w-full ${className} px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 flex items-center justify-center gap-1`}>
    <Icon name={icon} size={13} /> {label}
  </button>
);

// One client tile on the Clients page; clicking it expands compliance details, actions and cases.
export default function AccountCard({
  account: a, cases, isOpen, isSelected, onToggleOpen, onToggleSelected,
  onEdit, onDelete, onManageParties, onTrackRecord, onAttachments, onHistory,
}) {
  return (
    <div onClick={onToggleOpen}
      className={`bg-white border rounded-xl p-5 shadow-sm cursor-pointer hover:shadow-md transition-all ${isOpen ? "border-brand-400 ring-1 ring-brand-200" : "border-gray-100"}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <input type="checkbox" checked={isSelected} onClick={(e) => e.stopPropagation()}
            onChange={onToggleSelected} className="mt-1 flex-shrink-0" />
          <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm"
            style={{ background: "#1a3a5c" }}>
            {a.company_name.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-800">{a.company_name}</h3>
            <p className="text-xs text-gray-500">
              {a.account_type === "Individual"
                ? `${a.nationality || "—"} · ${a.occupation || "Individual"}`
                : `${a.industry || "—"} · ${a.country || "—"}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          {a.account_type === "Individual" && <Badge text="Individual" />}
          {a.is_pep && <Badge text="PEP" />}
          {a.profile_status && a.profile_status !== "New" && <Badge text={a.profile_status} />}
          <Badge text={a.strategic_priority} />
          {a.risk_rating && <Badge text={`${a.risk_rating} Risk`} />}
          <button onClick={onEdit} title="Edit" className="p-1.5 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600 ml-1">
            <Icon name="edit" size={14} />
          </button>
          <button onClick={onDelete} title="Delete" className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
            <Icon name="del" size={14} />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3 text-center">
        <Stat label="Invoiced" value={fmt(a.total_invoiced_amount)} />
        <Stat label="Cases" value={a.total_cases} />
        <Stat label="Existing" value={a.existing_relationship} />
      </div>
      {isOpen && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <p className="text-xs font-semibold text-gray-600 mb-2">Key Contacts</p>
          <p className="text-xs text-gray-600 mb-3">{a.key_contacts || "—"}</p>
          <p className="text-xs font-semibold text-gray-600 mb-2">Compliance</p>
          <div className="grid grid-cols-3 gap-3 text-center mb-3">
            <Stat small label="Reg. No." value={a.registration_number || "—"} />
            <Stat small label="License No." value={a.license_number || "—"} />
            <Stat small label="KYC Status" value={a.kyc_status || "—"} />
            <Stat small label="AML Class" value={a.aml_classification || "—"} />
            <Stat small label="Next AML Review" value={fmtDate(a.next_aml_review_date) || "—"} />
            <Stat small label="TRN/VAT" value={a.trn_vat_number || "—"} />
          </div>
          <ActionButton icon="accounts" label="Manage Shareholders / Directors / Signatories" onClick={onManageParties} />
          <ActionButton icon="download" label="Track Record" onClick={onTrackRecord} />
          <ActionButton icon="instructions" label="Attachments" onClick={onAttachments} />
          <ActionButton icon="activities" label="History (audit trail)" onClick={onHistory} className="mb-3" />
          <p className="text-xs font-semibold text-gray-600 mb-2">Cases ({cases.length})</p>
          <div className="space-y-1.5">
            {cases.map((c) => (
              <div key={c.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                <div className="flex-1 min-w-0 mr-2">
                  <div className="text-xs font-medium text-gray-700 truncate">{c.case_uid}</div>
                  <Badge text={c.stage} />
                </div>
                <span className="text-xs font-bold" style={{ color: "#1a3a5c" }}>{fmt(c.invoice_amount)}</span>
              </div>
            ))}
            {cases.length === 0 && <p className="text-xs text-gray-400">No cases yet.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
