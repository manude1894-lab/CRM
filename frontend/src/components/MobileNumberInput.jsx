import React, { useEffect, useId, useRef, useState } from "react";
import { digitsOnly, lengthProblem } from "../utils/mobile";
import { matchesDial } from "../utils/dialCodes";

/** Country code then number (Triam UAT 12-11-2026): the number takes digits only, and a number without a code is
 *  flagged at once. Triam UAT 27-11-2026: the code is searched by country name or ISD code ("india", "971", "+44"). */
function DialCodePicker({ code, options, onCode, disabled, invalid }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef(null);
  const listId = useId();
  const selected = options.find((o) => o.code === code);
  const shown = options.filter((o) => matchesDial(o, query));

  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const choose = (o) => { onCode(o.code); setOpen(false); setQuery(""); };
  const onKeyDown = (e) => {
    if (!open && ["ArrowDown", "Enter"].includes(e.key)) { e.preventDefault(); setOpen(true); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, shown.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && open) { e.preventDefault(); if (shown[active]) choose(shown[active]); }
    else if (e.key === "Escape") { setOpen(false); setQuery(""); }
  };

  return (
    <div className="relative w-44 flex-shrink-0">
      <input type="text" role="combobox" aria-label="Country code" aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
        aria-activedescendant={open && shown[active] ? `${listId}-${active}` : undefined} disabled={disabled} autoComplete="off"
        value={open ? query : selected?.label || ""} placeholder={open ? "Country or code…" : "Select"}
        onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onBlur={() => { setOpen(false); setQuery(""); }}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }} onKeyDown={onKeyDown}
        className={`w-full border rounded-lg pl-3 pr-7 py-2 text-sm truncate focus:outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 disabled:bg-gray-50 ${invalid ? "border-red-300" : "border-gray-200"}`} />
      <svg className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-gray-400" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 10l5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {open && !disabled && (
        <ul id={listId} ref={listRef} role="listbox" aria-label="Country codes"
          className="absolute z-30 mt-1 max-h-60 w-72 overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          {shown.length === 0 && <li className="px-3 py-2 text-xs text-gray-500">No country or code matches</li>}
          {shown.map((o, i) => (
            <li key={o.code} id={`${listId}-${i}`} data-index={i} role="option" aria-selected={o.code === code}
              onMouseDown={(e) => { e.preventDefault(); choose(o); }} onMouseEnter={() => setActive(i)}
              className={`cursor-pointer px-3 py-1.5 text-sm ${i === active ? "bg-brand-50 text-brand-800" : "text-gray-800"} ${o.code === code ? "font-semibold" : ""}`}>
              {o.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MobileNumberInput({ code, number, onCode, onNumber, options, placeholder = "e.g. 501234567", disabled = false }) {
  const missingCode = !!String(number || "").trim() && !code;
  // Triam UAT 28-11-2026: a number of the wrong length for its country is flagged once the user leaves the field.
  const [left, setLeft] = useState(false);
  const length = left && code && String(number || "").trim() ? lengthProblem(code, number) : null;
  const wrongLength = length ? `Check the number: ${length}.` : null;
  return (
    <div>
      <div className="flex gap-2">
        <DialCodePicker code={code} options={options} onCode={onCode} disabled={disabled} invalid={missingCode} />
        <input aria-label="Mobile number" type="text" inputMode="numeric" autoComplete="tel-national" maxLength={12} disabled={disabled}
          value={number || ""} placeholder={placeholder} onChange={(e) => onNumber(digitsOnly(e.target.value))}
          onBlur={() => setLeft(true)} aria-invalid={wrongLength ? true : undefined}
          className={`w-full border ${wrongLength ? "border-red-400" : "border-gray-200"} rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 disabled:bg-gray-50`} />
      </div>
      {missingCode && <p className="text-[11px] text-red-500 mt-1">Select the country code.</p>}
      {wrongLength && <p role="alert" className="text-xs text-red-700 mt-1">{wrongLength}</p>}
    </div>
  );
}
