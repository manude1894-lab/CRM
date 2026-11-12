import React from "react";
import { digitsOnly } from "../utils/mobile";

/** Country code then number (Triam UAT 12-11-2026): the code list starts at "Select", which can't be
 *  chosen, and the number takes digits only. A number without a code is flagged at once. */
export default function MobileNumberInput({ code, number, onCode, onNumber, options, placeholder = "e.g. 501234567", disabled = false }) {
  const missingCode = !!String(number || "").trim() && !code;
  return (
    <div>
      <div className="flex gap-2">
        <select aria-label="Country code" value={code || ""} disabled={disabled} onChange={(e) => onCode(e.target.value)}
          className={`!w-44 w-44 flex-shrink-0 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand-400 disabled:bg-gray-50 ${missingCode ? "border-red-300" : "border-gray-200"} ${code ? "" : "text-gray-400"}`}>
          <option value="" disabled>Select</option>
          {options.map((c) => <option key={c.code} value={c.code} className="text-gray-900">{c.label}</option>)}
        </select>
        <input aria-label="Mobile number" type="text" inputMode="numeric" autoComplete="tel-national" maxLength={12} disabled={disabled}
          value={number || ""} placeholder={placeholder} onChange={(e) => onNumber(digitsOnly(e.target.value))}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 disabled:bg-gray-50" />
      </div>
      {missingCode && <p className="text-[11px] text-red-500 mt-1">Select the country code.</p>}
    </div>
  );
}
