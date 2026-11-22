import React, { useEffect, useMemo, useState } from "react";
import { Button } from "./ui";

/**
 * Lists people can page through and sort (Triam 22-11-2026): a rows-per-page choice under every list, and column
 * headers that sort with an arrow. The chosen page size is remembered per list in this browser.
 */
export const PAGE_SIZES = [15, 50, 100, 200];

function readSize(key, fallback) {
  try {
    const n = Number(localStorage.getItem(`triam.pageSize.${key}`));
    return PAGE_SIZES.includes(n) ? n : fallback;
  } catch { return fallback; }
}

/** The page size of one list, remembered in this browser. */
export function usePageSize(key, fallback = 50) {
  const [size, setSize] = useState(() => readSize(key, fallback));
  const change = (n) => {
    setSize(n);
    try { localStorage.setItem(`triam.pageSize.${key}`, String(n)); } catch { /* private window: not remembered */ }
  };
  return [size, change];
}

/** The page numbers to offer: first, last, and two either side of the current one. */
export function pageNumbers(page, pages) {
  const wanted = new Set([0, pages - 1, page - 2, page - 1, page, page + 1, page + 2]);
  const list = [...wanted].filter((n) => n >= 0 && n < pages).sort((a, b) => a - b);
  return list.flatMap((n, i) => (i && n - list[i - 1] > 1 ? ["…", n] : [n]));
}

export function Pager({ page, pageSize, total, onPage, onPageSize, busy = false, label = "rows" }) {
  if (!total) return null;
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav aria-label="Pages" className={`flex flex-wrap items-center justify-between gap-3 text-xs text-gray-600 ${busy ? "opacity-60" : ""}`}>
      <span className="flex items-center gap-3">
        <span>{`Showing ${page * pageSize + 1}–${Math.min(total, (page + 1) * pageSize)} of ${total}`}</span>
        <label className="flex items-center gap-1.5">
          <span>Rows per page</span>
          <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))} aria-label={`${label} per page`}
            className="border border-gray-200 rounded-md bg-white px-1.5 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-300">
            {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </span>
      {pages > 1 && (
        <span className="flex items-center gap-1">
          <Button size="sm" disabled={page === 0 || busy} onClick={() => onPage(page - 1)}>Previous</Button>
          {pageNumbers(page, pages).map((n, i) => (n === "…"
            ? <span key={`gap${i}`} className="px-1 text-gray-500">…</span>
            : <button key={n} type="button" onClick={() => onPage(n)} disabled={busy} aria-current={n === page ? "page" : undefined}
                aria-label={`Page ${n + 1}`}
                className={`min-w-[28px] h-7 px-1.5 rounded-md text-xs ${n === page ? "bg-brand-600 text-white font-semibold" : "text-gray-700 hover:bg-gray-100"}`}>
                {n + 1}
              </button>))}
          <Button size="sm" disabled={page + 1 >= pages || busy} onClick={() => onPage(page + 1)}>Next</Button>
        </span>
      )}
    </nav>
  );
}

/** A column header that sorts. `sort` is { by, dir } ("asc" / "desc"); clicking a new column sorts it ascending
 * (dates: newest first), clicking again flips it. */
export function SortTh({ label, by, sort, onSort, firstDir = "asc", className = "" }) {
  const active = sort?.by === by;
  const dir = active ? sort.dir : null;
  const next = active ? (dir === "asc" ? "desc" : "asc") : firstDir;
  return (
    <th aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"} className={`py-2.5 px-3 font-semibold text-left whitespace-nowrap ${className}`}>
      <button type="button" onClick={() => onSort({ by, dir: next })} title={`Sort by ${label}`}
        className={`inline-flex items-center gap-1 uppercase tracking-wide hover:text-gray-800 ${active ? "text-gray-800" : ""}`}>
        {label}
        <svg width="9" height="12" viewBox="0 0 9 12" aria-hidden="true" className="flex-shrink-0">
          <path d="M4.5 0.5 L8 4.5 H1 Z" fill="currentColor" opacity={dir === "asc" ? 1 : 0.3} />
          <path d="M4.5 11.5 L8 7.5 H1 Z" fill="currentColor" opacity={dir === "desc" ? 1 : 0.3} />
        </svg>
      </button>
    </th>
  );
}

// Compares two cell values: numbers as numbers, dates (YYYY-MM-DD...) and text as text; blanks last.
const BLANK = (v) => v == null || v === "" || v === "—";
export function compareValues(a, b) {
  if (BLANK(a) || BLANK(b)) return BLANK(a) === BLANK(b) ? 0 : BLANK(a) ? 1 : -1;
  const na = typeof a === "number" ? a : Number(a), nb = typeof b === "number" ? b : Number(b);
  if (!Number.isNaN(na) && !Number.isNaN(nb) && String(a).trim() !== "" && String(b).trim() !== "") return na - nb;
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
}

export function sortRows(rows, sort, valueOf) {
  if (!sort?.by && sort?.by !== 0) return rows;
  const sign = sort.dir === "desc" ? -1 : 1;
  return [...rows].sort((x, y) => {
    const a = valueOf(x, sort.by), b = valueOf(y, sort.by);
    if (BLANK(a) || BLANK(b)) return compareValues(a, b); // blanks stay last either way
    return sign * compareValues(a, b);
  });
}

/** Paging and sorting of a list already in the browser. `resetOn` lists what starts the list again at page 1. */
export function useListView(rows, { key, defaultSize = 50, defaultSort = null, valueOf = (r, by) => r[by], resetOn = [] }) {
  const [pageSize, setPageSize] = usePageSize(key, defaultSize);
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState(defaultSort);
  useEffect(() => { setPage(0); }, [pageSize, sort?.by, sort?.dir, rows.length, ...resetOn]);
  const sorted = useMemo(() => sortRows(rows, sort, valueOf), [rows, sort]);
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pages - 1);
  return {
    rows: sorted.slice(current * pageSize, (current + 1) * pageSize), all: sorted,
    sort, setSort, pager: { page: current, pageSize, total: sorted.length, onPage: setPage, onPageSize: setPageSize },
  };
}
