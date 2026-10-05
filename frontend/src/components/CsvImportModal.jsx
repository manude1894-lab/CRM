import React, { useRef, useState } from "react";
import { Modal } from "./ui";
import { parseCSVTable } from "./accounts/accountCsv";
import { toast } from "../store/toast";

const STATUS = {
  ok: <span className="text-emerald-600 font-medium">Will import</span>,
  duplicate: <span className="text-amber-600 font-medium">Already in CRM</span>,
  error: <span className="text-red-600 font-medium">Error</span>,
};

const key = (h) => (h || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

/**
 * Generic CSV import with a dry run (P6 data migration). The file's headers are matched to field
 * names through `columns` ([field, label, ...aliases]); the server checks every row and nothing is
 * saved until the user confirms the preview.
 *   onRun(rows, dryRun) → [{ row_index, company_name, status, message }]
 */
export default function CsvImportModal({ title, columns, required = [], templateName, onRun, onClose, onDone }) {
  const fileRef = useRef(null);
  const [rows, setRows] = useState(null);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);

  const lookup = {};
  columns.forEach(([field, label, ...aliases]) => [field, label, ...aliases].forEach((a) => { lookup[key(a)] = field; }));

  const downloadTemplate = () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([columns.map((c) => c[1]).join(",") + "\n"], { type: "text/csv" }));
    a.download = templateName; a.click();
  };

  const read = async (file) => {
    const table = parseCSVTable(await file.text());
    if (table.length < 2) return toast.error("The file has no data rows.");
    const fields = table[0].map((h) => lookup[key(h)] || null);
    const missing = required.filter((f) => !fields.includes(f));
    if (missing.length) return toast.error(`Missing column(s): ${missing.map((f) => columns.find((c) => c[0] === f)[1]).join(", ")}`);
    const parsed = table.slice(1).map((r) => Object.fromEntries(fields.map((f, i) => [f, (r[i] ?? "").trim()]).filter(([f]) => f)));
    setBusy(true);
    try { setRows(parsed); setResults(await onRun(parsed, true)); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not check the file"); }
    finally { setBusy(false); }
  };

  const confirm = async () => {
    setBusy(true);
    try {
      const done = await onRun(rows, false);
      const n = done.filter((r) => r.status === "ok").length;
      toast.success(`Imported ${n} row${n === 1 ? "" : "s"}`);
      onDone?.();
      onClose();
    } catch (e) { toast.error(e.response?.data?.detail || "Import failed"); } finally { setBusy(false); }
  };

  const count = (s) => (results || []).filter((r) => r.status === s).length;
  return (
    <Modal title={title} onClose={onClose}>
      {!results ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-600">Choose a CSV file (save the Excel sheet as CSV). The first row must hold the column names below; other columns are ignored. Dates as DD/MM/YYYY.</p>
          <div className="flex flex-wrap gap-1">
            {columns.map(([f, label]) => (
              <span key={f} className={`text-[11px] px-1.5 py-0.5 rounded border ${required.includes(f) ? "border-brand-300 text-brand-700 bg-brand-50" : "border-gray-200 text-gray-500"}`}>
                {label}{required.includes(f) ? " *" : ""}
              </span>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input ref={fileRef} type="file" accept=".csv,text/csv" disabled={busy}
              onChange={(e) => { const f = e.target.files?.[0]; if (f) read(f); e.target.value = ""; }}
              className="text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
            <button onClick={downloadTemplate} className="text-xs text-brand-600 hover:underline">Download a blank template</button>
          </div>
          {busy && <p className="text-xs text-gray-400">Checking the file…</p>}
        </div>
      ) : (
        <div>
          <p className="text-sm text-gray-600 mb-3">
            {count("ok")} of {results.length} rows will be imported · {count("duplicate")} already in the CRM · {count("error")} with errors (skipped).
          </p>
          <div className="max-h-80 overflow-y-auto border border-gray-100 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left p-2 font-semibold text-gray-600">Row</th>
                  <th className="text-left p-2 font-semibold text-gray-600">Company</th>
                  <th className="text-left p-2 font-semibold text-gray-600">Result</th>
                  <th className="text-left p-2 font-semibold text-gray-600">Note</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.row_index} className="border-t border-gray-100">
                    <td className="p-2 text-gray-400">{r.row_index + 2}</td>
                    <td className="p-2 text-gray-700">{r.company_name || "—"}</td>
                    <td className="p-2">{STATUS[r.status]}</td>
                    <td className="p-2 text-gray-500">{r.message || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={() => setResults(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Choose another file</button>
            <button onClick={confirm} disabled={busy || count("ok") === 0}
              className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50" style={{ background: "#1a3a5c" }}>
              {busy ? "Importing…" : `Import ${count("ok")} row${count("ok") === 1 ? "" : "s"}`}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
