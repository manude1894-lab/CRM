import React, { useMemo, useState } from "react";
import { Icon, Badge } from "./ui";
import { AR_FILING_STATUS_OPTIONS } from "../utils/constants";

const DAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const urgencyClass = (r) => {
  const threshold = r.item === "bo_filing" ? 14 : 7;
  if (r.days_remaining <= threshold) return "bg-red-100 text-red-700";
  if (r.days_remaining <= 30) return "bg-amber-100 text-amber-700";
  return "bg-gray-100 text-gray-600";
};

const toKey = (d) => {
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, "0"), day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};

export default function ComplianceCalendar({ rows, itemLabel, onMarkDone, onSetArStatus }) {
  const [monthCursor, setMonthCursor] = useState(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState(null);

  const itemsByDate = useMemo(() => {
    const map = {};
    for (const r of rows) {
      if (!r.due_date) continue;
      (map[r.due_date] ||= []).push(r);
    }
    return map;
  }, [rows]);

  const weeks = useMemo(() => {
    const start = new Date(monthCursor);
    start.setDate(start.getDate() - start.getDay()); // back up to the Sunday on/before the 1st
    const days = [];
    const cursor = new Date(start);
    for (let i = 0; i < 42; i++) {
      days.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    const grid = [];
    for (let i = 0; i < 42; i += 7) grid.push(days.slice(i, i + 7));
    return grid;
  }, [monthCursor]);

  const monthLabel = monthCursor.toLocaleDateString("en-US", { month: "long", year: "numeric" });
  const selectedRows = selectedDate ? (itemsByDate[selectedDate] || []) : [];

  return (
    <div className="space-y-3">
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <button onClick={() => setMonthCursor((c) => new Date(c.getFullYear(), c.getMonth() - 1, 1))}
            className="p-1.5 rounded hover:bg-gray-50 text-gray-400 hover:text-gray-600">
            <Icon name="chevronLeft" size={16} />
          </button>
          <span className="text-sm font-semibold text-gray-800">{monthLabel}</span>
          <button onClick={() => setMonthCursor((c) => new Date(c.getFullYear(), c.getMonth() + 1, 1))}
            className="p-1.5 rounded hover:bg-gray-50 text-gray-400 hover:text-gray-600">
            <Icon name="chevronRight" size={16} />
          </button>
        </div>
        <p className="text-[11px] text-gray-400 mb-2">Only shows items within the selected day-window above — browsing past that range will look empty.</p>

        <div className="grid grid-cols-7 gap-1">
          {DAY_LABELS.map((d) => (
            <div key={d} className="text-center text-[10px] font-semibold text-gray-400 uppercase py-1">{d}</div>
          ))}
          {weeks.flat().map((date) => {
            const key = toKey(date);
            const inMonth = date.getMonth() === monthCursor.getMonth();
            const items = itemsByDate[key] || [];
            const isSelected = selectedDate === key;
            return (
              <button
                key={key}
                onClick={() => setSelectedDate(items.length ? key : null)}
                className={`text-left min-h-[64px] rounded-lg border p-1.5 transition-colors ${
                  isSelected ? "border-brand-300 bg-brand-50" : "border-gray-100 hover:bg-gray-50"
                } ${inMonth ? "" : "opacity-40"}`}
              >
                <div className="text-[11px] font-medium text-gray-500 mb-1">{date.getDate()}</div>
                <div className="space-y-0.5">
                  {items.slice(0, 3).map((r, i) => (
                    <div key={i} className={`text-[10px] px-1 py-0.5 rounded truncate ${urgencyClass(r)}`}>
                      {r.company_name}
                    </div>
                  ))}
                  {items.length > 3 && (
                    <div className="text-[10px] text-gray-400 px-1">+{items.length - 3} more</div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selectedDate && (
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4">
          <p className="text-sm font-semibold text-gray-800 mb-3">{selectedDate} — {selectedRows.length} item{selectedRows.length !== 1 ? "s" : ""}</p>
          <div className="space-y-2">
            {selectedRows.map((r, i) => (
              <div key={i} className="flex items-center justify-between p-2.5 bg-gray-50 rounded-lg">
                <div>
                  <div className="text-xs font-medium text-gray-800">{r.company_name} <span className="text-gray-400">({r.case_uid})</span></div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {r.label || itemLabel[r.item] || r.item}
                    {r.item === "bo_filing" && <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700">30-day</span>}
                    {r.item === "ar_filing" && r.ar_filing_status && (
                      <span className="ml-1.5 inline-flex items-center gap-1.5">
                        <Badge text={r.ar_filing_status} />
                        <select value={r.ar_filing_status} onChange={(e) => onSetArStatus(r, e.target.value)}
                          className="text-[11px] border border-gray-200 rounded px-1 py-0.5 focus:outline-none">
                          {AR_FILING_STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </span>
                    )}
                  </div>
                </div>
                <button onClick={() => onMarkDone(r)}
                  className="p-1.5 rounded hover:bg-green-50 text-gray-400 hover:text-green-600 flex-shrink-0" title="Mark done">
                  <Icon name="check" size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
