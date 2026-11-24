import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { useFieldLabel } from "./ui";

/**
 * Choosing a client from a long list (Triam 24-11-2026): type to search by name, Client ID or temporary ID.
 * Each option shows the client's name first, with its Client ID and status beside it, sorted by name.
 * Keyboard: arrows move, Enter picks, Escape closes. `allLabel` adds an "all clients" choice (for filters).
 */
export const clientRef = (c) => c.client_id || c.temp_id || c.account_uid || "";

export function matchClients(clients, query) {
  const q = query.trim().toLowerCase();
  const sorted = [...clients].sort((a, b) => (a.company_name || "").localeCompare(b.company_name || "", undefined, { sensitivity: "base" }));
  if (!q) return sorted;
  const starts = [], contains = [];
  for (const c of sorted) {
    const name = (c.company_name || "").toLowerCase();
    const ids = [c.client_id, c.temp_id, c.account_uid, c.search_name].map((v) => (v || "").toLowerCase());
    if (name.startsWith(q) || ids.some((v) => v.startsWith(q))) starts.push(c);
    else if (name.includes(q) || ids.some((v) => v.includes(q))) contains.push(c);
  }
  return [...starts, ...contains]; // names beginning with the text first
}

export default function ClientPicker({ clients = [], value, onChange, allLabel, placeholder = "Search client name or Client ID…",
  disabled = false, className = "", ...rest }) {
  const label = useFieldLabel(rest);
  const listId = useId();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const box = useRef(null);
  const list = useRef(null);
  const chosen = clients.find((c) => String(c.id) === String(value));
  const matches = useMemo(() => matchClients(clients, query), [clients, query]);
  // "All clients" is offered until something is typed; then Enter picks the best match, not "all".
  const options = [...(allLabel && !query.trim() ? [{ id: "", all: true }] : []), ...matches];

  useEffect(() => {
    const away = (e) => { if (box.current && !box.current.contains(e.target)) { setOpen(false); setQuery(""); } };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);
  useEffect(() => { setActive(0); }, [query, open]);
  useEffect(() => { list.current?.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" }); }, [active]);

  const pick = (opt) => { onChange(opt.all ? "" : String(opt.id)); setOpen(false); setQuery(""); };
  const keys = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); if (!open) setOpen(true); else setActive((i) => Math.min(i + 1, options.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter" && open && options[active]) { e.preventDefault(); pick(options[active]); }
    else if (e.key === "Escape") { setOpen(false); setQuery(""); }
  };
  const shown = open ? query : chosen ? `${chosen.company_name}${clientRef(chosen) ? ` (${clientRef(chosen)})` : ""}` : allLabel && !value ? allLabel : "";

  return (
    <div ref={box} className={`relative ${className}`}>
      <input type="text" role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list"
        aria-activedescendant={open && options[active] ? `${listId}-${active}` : undefined}
        {...label} aria-label={rest["aria-label"]} disabled={disabled}
        value={shown} placeholder={chosen || (allLabel && !value) ? undefined : placeholder}
        onFocus={() => setOpen(true)} onClick={() => setOpen(true)}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }} onKeyDown={keys}
        className="w-full border border-gray-200 rounded-lg pl-3 pr-8 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300 focus:border-brand-400 disabled:bg-gray-50 disabled:text-gray-500" />
      <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12" className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
        <path d="M2 4.5 L6 8.5 L10 4.5" stroke="currentColor" strokeWidth="1.6" fill="none" />
      </svg>
      {open && (
        <ul id={listId} role="listbox" ref={list}
          className="absolute z-50 mt-1 w-full min-w-[20rem] max-h-80 overflow-auto bg-white border border-gray-200 rounded-lg shadow-lg py-1 text-sm">
          {options.length === 0 && <li className="px-3 py-2 text-gray-500">No client matches “{query}”</li>}
          {options.map((o, i) => (
            <li key={o.all ? "all" : o.id} id={`${listId}-${i}`} data-i={i} role="option" aria-selected={String(o.id) === String(value ?? "")}
              onMouseDown={(e) => { e.preventDefault(); pick(o); }} onMouseEnter={() => setActive(i)}
              className={`px-3 py-1.5 cursor-pointer ${i === active ? "bg-brand-50" : ""}`}>
              {o.all ? <span className="text-gray-700">{allLabel}</span> : (
                <>
                  <span className="block text-gray-900 leading-snug">{o.company_name}</span>
                  <span className="block text-[11px] text-gray-500 leading-snug">
                    <span className="font-mono">{clientRef(o) || "—"}</span>{o.profile_status ? ` · ${o.profile_status}` : ""}
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
