import React, { useEffect, useMemo, useRef, useState } from "react";
import { documentsApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon } from "./ui";
import { DOCUMENT_CATEGORY_OPTIONS } from "../utils/constants";
import GenerateDocModal from "./GenerateDocModal";

const fmtBytes = (b) =>
  b == null ? "" : b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1048576).toFixed(1)} MB`;

const isViewable = (ct) => {
  const t = (ct || "").toLowerCase();
  return t.startsWith("application/pdf") || t.startsWith("image/");
};

/**
 * Reusable attachments list + uploader.
 *
 * props:
 *   caseId   — required
 *   scope    — { case_document_id } | { instruction_id } | { category } | null (all case docs)
 *   compact  — tighter layout for inline use under a checklist row
 *   onChange — called after a successful upload/delete (e.g. to refresh a checklist)
 */
export default function DocumentsPanel({ caseId, scope = null, compact = false, defaultCategory, onChange }) {
  const user = useAuthStore((s) => s.user);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [category, setCategory] = useState(
    scope?.category || defaultCategory || (scope?.case_document_id ? "CDD" : "Other")
  );
  const [notes, setNotes] = useState("");
  const [genOpen, setGenOpen] = useState(false);
  const fileRef = useRef(null);

  const load = async () => {
    setLoading(true);
    try { setDocs(await documentsApi.list(caseId)); }
    catch { setDocs([]); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (caseId) load(); }, [caseId]);

  const filtered = useMemo(() => docs.filter((d) => {
    if (scope?.case_document_id) return d.case_document_id === scope.case_document_id;
    if (scope?.instruction_id) return d.instruction_id === scope.instruction_id;
    if (scope?.category) return d.category === scope.category && !d.case_document_id && !d.instruction_id;
    if (scope === null) return !d.case_document_id && !d.instruction_id;
    return true;
  }), [docs, scope]);

  const canDelete = (d) => user?.role === "admin" || d.uploaded_by_id === user?.id;

  const doUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", category);
      if (scope?.case_document_id) fd.append("case_document_id", scope.case_document_id);
      if (scope?.instruction_id) fd.append("instruction_id", scope.instruction_id);
      if (notes.trim()) fd.append("notes", notes.trim());
      await documentsApi.upload(caseId, fd);
      fileRef.current.value = "";
      setNotes("");
      await load();
      onChange?.();
    } catch (e) {
      alert(e.response?.data?.detail || "Upload failed");
    } finally { setBusy(false); }
  };

  const doDelete = async (d) => {
    if (!confirm(`Delete "${d.filename}"?`)) return;
    try { await documentsApi.remove(d.id); await load(); onChange?.(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className={compact ? "space-y-1.5" : "space-y-2"}>
      {loading ? (
        <p className="text-xs text-gray-400">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No files attached.</p>
      ) : (
        <div className="space-y-1">
          {filtered.map((d) => (
            <div key={d.id} className="flex items-center justify-between gap-2 p-1.5 bg-gray-50 rounded-lg">
              <button onClick={() => documentsApi.download(d.id, d.filename)}
                className="flex items-center gap-1.5 min-w-0 text-xs text-blue-600 hover:underline">
                <Icon name="download" size={12} className="flex-shrink-0" />
                <span className="truncate">{d.filename}</span>
              </button>
              <div className="flex items-center gap-2 flex-shrink-0 text-[11px] text-gray-400">
                {isViewable(d.content_type) && (
                  <button onClick={() => documentsApi.view(d.id)} title="View"
                    className="p-0.5 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600">
                    <Icon name="view" size={12} />
                  </button>
                )}
                {d.generated_from && <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">generated</span>}
                {!compact && !scope?.category && <span className="px-1.5 py-0.5 rounded bg-gray-100">{d.category}</span>}
                <span>{fmtBytes(d.size_bytes)}</span>
                <span>{(d.created_at || "").slice(0, 10)}</span>
                {canDelete(d) && (
                  <button onClick={() => doDelete(d)} className="p-0.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-500">
                    <Icon name="del" size={12} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className={`flex flex-wrap items-center gap-2 ${compact ? "" : "pt-1"}`}>
        <input ref={fileRef} type="file" className="text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
        {!scope?.case_document_id && !scope?.category && (
          <select value={category} onChange={(e) => setCategory(e.target.value)}
            className="border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-blue-400">
            {DOCUMENT_CATEGORY_OPTIONS.map((c) => <option key={c}>{c}</option>)}
          </select>
        )}
        {!compact && (
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Note (e.g. certified by…)"
            className="flex-1 min-w-40 border border-gray-200 rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-blue-400" />
        )}
        <button onClick={doUpload} disabled={busy}
          className="px-2.5 py-1 text-xs text-white rounded-lg disabled:opacity-60" style={{ background: "#2B6D9A" }}>
          {busy ? "Uploading…" : "Upload"}
        </button>
        {!compact && !scope?.case_document_id && (
          <button onClick={() => setGenOpen(true)}
            className="px-2.5 py-1 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">
            Generate
          </button>
        )}
      </div>

      {genOpen && (
        <GenerateDocModal caseId={caseId} onClose={(created) => { setGenOpen(false); if (created) { load(); onChange?.(); } }} />
      )}
    </div>
  );
}
