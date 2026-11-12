import React from "react";
import { CURRENCIES } from "../utils/constants";

/** Currency then amount, side by side (Triam UAT 10-11-2026 row 57: the currency comes before the amount). */
export default function MoneyInput({ currency, amount, onCurrency, onAmount, disabled = false, label = "Amount" }) {
  return (
    <div className="flex gap-2">
      <select aria-label={`${label} currency`} value={currency || "AED"} disabled={disabled} onChange={(e) => onCurrency(e.target.value)}
        className="w-24 shrink-0 border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:border-brand-400 disabled:bg-gray-50">
        {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
      </select>
      <input aria-label={label} type="number" min="0" step="0.01" value={amount ?? ""} disabled={disabled} onChange={(e) => onAmount(e.target.value)}
        className="w-full min-w-0 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 disabled:bg-gray-50" />
    </div>
  );
}
