import React from "react";
import { Modal } from "../ui";

const STATUS_LABELS = {
  ok: <span className="text-emerald-600 font-medium">Will create</span>,
  duplicate: <span className="text-amber-600 font-medium">Duplicate</span>,
  error: <span className="text-red-600 font-medium">Error</span>,
};

// Dry-run results of a client CSV import; the user confirms before anything is created.
export default function ImportPreviewModal({ results, importing, onConfirm, onClose }) {
  const count = (status) => results.filter((r) => r.status === status).length;
  const okCount = count("ok");
  return (
    <Modal title="Import Clients — Preview" onClose={onClose}>
      <p className="text-sm text-gray-600 mb-3">
        {okCount} of {results.length} rows will be created.
        {" "}{count("duplicate")} duplicate(s), {" "}
        {count("error")} error(s) will be skipped.
      </p>
      <div className="max-h-80 overflow-y-auto border border-gray-100 rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              <th className="text-left p-2 font-semibold text-gray-600">Row</th>
              <th className="text-left p-2 font-semibold text-gray-600">Company Name</th>
              <th className="text-left p-2 font-semibold text-gray-600">Status</th>
              <th className="text-left p-2 font-semibold text-gray-600">Note</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.row_index} className="border-t border-gray-100">
                <td className="p-2 text-gray-400">{r.row_index + 1}</td>
                <td className="p-2 text-gray-700">{r.company_name || "—"}</td>
                <td className="p-2">{STATUS_LABELS[r.status]}</td>
                <td className="p-2 text-gray-400">{r.message || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex justify-end gap-3 mt-5">
        <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={onConfirm} disabled={importing || okCount === 0}
          className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
          style={{ background: "#1a3a5c" }}>
          {importing ? "Importing..." : `Import ${okCount} Client(s)`}
        </button>
      </div>
    </Modal>
  );
}
