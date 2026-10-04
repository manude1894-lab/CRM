import React from "react";
import { Select } from "../ui";
import { RISK_OPTIONS, KYC_STATUS_OPTIONS } from "./accountForm";

const BulkField = ({ value, placeholder, options, disabled, onChange, onApply }) => (
  <div className="flex items-center gap-1.5">
    <Select value={value} onChange={(e) => onChange(e.target.value)} className="text-xs">
      <option value="">{placeholder}</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </Select>
    <button disabled={!value || disabled} onClick={onApply}
      className="px-2.5 py-1.5 text-xs border border-brand-300 rounded-lg bg-white hover:bg-brand-100 disabled:opacity-40">Apply</button>
  </div>
);

const asOptions = (list) => list.map((v) => ({ value: v, label: v }));

// Shown when one or more clients are ticked; applies one field at a time to every selected client.
export default function BulkActionBar({ count, users, values, onChange, onApply, applying, onClear }) {
  const field = (key, placeholder, options) => (
    <BulkField value={values[key]} placeholder={placeholder} options={options} disabled={applying}
      onChange={(v) => onChange({ ...values, [key]: v })} onApply={() => onApply(key)} />
  );
  return (
    <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3 flex items-center flex-wrap gap-3">
      <span className="text-xs font-medium text-brand-700">{count} selected</span>
      {field("spoc_id", "Anchor RM…", users.filter((u) => u.role === "rm").map((u) => ({ value: u.id, label: u.name })))}
      {field("risk_rating", "Risk Rating…", asOptions(RISK_OPTIONS))}
      {field("kyc_status", "KYC Status…", asOptions(KYC_STATUS_OPTIONS))}
      <button onClick={onClear} className="text-xs text-brand-500 hover:underline ml-auto">Clear selection</button>
    </div>
  );
}
