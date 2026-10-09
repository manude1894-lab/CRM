import React, { useEffect, useRef, useState } from "react";
import { documentsApi } from "../../api/endpoints";
import { Icon } from "../ui";
import { toast } from "../../store/toast";
import { confirmDialog } from "../../store/confirm";
import { useMasters } from "../../hooks/useMasters";
import { selectableCodes } from "../../hooks/masterUtils";
import { DOCUMENT_CATEGORY_OPTIONS, fmtDate } from "../../utils/constants";

const fmtBytes = (b) =>
  b == null ? "" : b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1048576).toFixed(1)} MB`;
const isViewable = (ct) => /^(application\/pdf|image\/)/i.test(ct || "");

const STAGE = {
  Draft: { style: "bg-blue-50 text-blue-700", note: "Documents can be added and removed while the client is being prepared." },
  Submitted: { style: "bg-amber-100 text-amber-800", note: "The client has been submitted — only an Approver can remove documents." },
  Locked: { style: "bg-gray-200 text-gray-700", note: "The client is approved — documents can be added but no longer removed." },
};

/**
 * BRD §16 — the client's document folder: everything filed against the Client ID, grouped by category,
 * plus documents attached to the client's cases. Removal follows the client's stage (Draft / Submitted /
 * Locked), decided by the server. The upload form opens only when the user chooses to upload (BRD §14).
 */
export default function ClientDocumentsFolder({ accountId, onChange, onboarding = false }) {
  const [folder, setFolder] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [category, setCategory] = useState("");
  const [notes, setNotes] = useState("");
  const [mode, setMode] = useState("file"); // "file" | "link" (Triam mark-up §14: URLs are allowed)
  const [linkUrl, setLinkUrl] = useState("");
  const [linkTitle, setLinkTitle] = useState("");
  const [openCats, setOpenCats] = useState({});
  const fileRef = useRef(null);
  const cats = useMasters("document_category", DOCUMENT_CATEGORY_OPTIONS);

  const load = () => documentsApi.folder(accountId).then(setFolder).catch(() => setFolder(null));
  useEffect(() => { if (accountId) load(); }, [accountId]);
  if (!folder) return <p className="text-xs text-gray-400">Loading documents…</p>;

  const groups = {};
  folder.documents.forEach((d) => { (groups[d.category] = groups[d.category] || []).push(d); });
  const stage = STAGE[folder.stage] || STAGE.Draft;
  const statusLocked = folder.profile_status === "Awaiting Approval" || folder.profile_status === "Exited";
  // Compliance files the CDD Form / AML Risk Assessment, also while the client is with Compliance.
  const complianceOnly = (code) => !!cats.items.find((i) => i.code === code)?.meta?.compliance_only;
  const locked = statusLocked && !folder.compliance_can_file;
  const categoryOptions = selectableCodes(cats.items, category)
    .filter((c) => !complianceOnly(c) || folder.compliance_can_file)
    .filter((c) => !statusLocked || complianceOnly(c));
  const sectionOf = (code) => cats.items.find((i) => i.code === code)?.meta?.section;

  const upload = async () => {
    if (mode === "link") return addLink();
    const file = fileRef.current?.files?.[0];
    if (!category) return toast.error("Choose a document category");
    if (!file) return toast.error("Choose a file to upload");
    if (file.size > folder.max_upload_mb * 1024 * 1024) return toast.error(`The file is ${fmtBytes(file.size)} — the limit is ${folder.max_upload_mb} MB per document.`);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", category);
      if (notes.trim()) fd.append("notes", notes.trim());
      await documentsApi.uploadForAccount(accountId, fd);
      toast.success(`Uploaded to ${cats.labelOf(category)}`);
      setOpenCats((o) => ({ ...o, [category]: true }));
      fileRef.current.value = ""; setNotes(""); setCategory(""); setUploading(false);
      await load();
      onChange?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally { setBusy(false); }
  };

  const addLink = async () => {
    if (!category) return toast.error("Choose a document category");
    if (!/^https:\/\/\S+$/i.test(linkUrl.trim())) return toast.error("Enter a valid https:// link");
    setBusy(true);
    try {
      await documentsApi.addLink(accountId, { category, url: linkUrl.trim(), title: linkTitle.trim() || null, notes: notes.trim() || null });
      toast.success(`Link added to ${cats.labelOf(category)}`);
      setOpenCats((o) => ({ ...o, [category]: true }));
      setLinkUrl(""); setLinkTitle(""); setNotes(""); setCategory(""); setUploading(false);
      await load();
      onChange?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not add the link");
    } finally { setBusy(false); }
  };

  const remove = async (d) => {
    if (!(await confirmDialog(`Remove "${d.filename}" from the client folder?`))) return;
    try { await documentsApi.remove(d.id); await load(); onChange?.(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not remove the document"); }
  };

  const Row = ({ d }) => (
    <div className="flex items-center justify-between gap-2 px-2 py-1.5 bg-white border border-gray-100 rounded">
      <div className="min-w-0">
        {d.link_url ? (
          <a href={d.link_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-xs text-brand-600 hover:underline min-w-0">
            <Icon name="link" size={12} className="flex-shrink-0" /><span className="truncate">{d.filename}</span>
          </a>
        ) : (
          <button onClick={() => documentsApi.download(d.id, d.filename)} className="flex items-center gap-1.5 text-xs text-brand-600 hover:underline min-w-0">
            <Icon name="download" size={12} className="flex-shrink-0" /><span className="truncate">{d.filename}</span>
          </button>
        )}
        <div className="text-[10px] text-gray-400">
          {d.link_url ? "Link" : fmtBytes(d.size_bytes)} · {fmtDate(d.created_at)}{d.uploaded_by_name ? ` · ${d.uploaded_by_name}` : ""}
          {d.case_uid && <> · case <span className="font-mono">{d.case_uid}</span></>}
          {d.notes && <> · {d.notes}</>}
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {!d.link_url && isViewable(d.content_type) && (
          <button onClick={() => documentsApi.view(d.id)} title="View" className="p-1 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600">
            <Icon name="view" size={13} />
          </button>
        )}
        {!d.case_uid && (d.can_delete
          ? <button onClick={() => remove(d)} title="Remove" className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={13} /></button>
          : <span title={d.lock_reason || ""} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 cursor-help">{d.stage === "Locked" ? "Locked" : "Protected"}</span>)}
      </div>
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-gray-500">Client folder</span>
        <span className="font-mono font-semibold text-gray-800">{folder.client_id || folder.temp_id || "—"}</span>
        <span className={`px-2 py-0.5 rounded font-semibold ${stage.style}`}>{folder.stage}</span>
        <span className="text-gray-400">{folder.documents.length} document{folder.documents.length === 1 ? "" : "s"}</span>
        {!locked && !uploading && (
          <button onClick={() => setUploading(true)} className="ml-auto px-2.5 py-1 text-xs text-white rounded-lg flex items-center gap-1" style={{ background: "#1a3a5c" }}>
            <Icon name="plus" size={12} /> Upload document
          </button>
        )}
      </div>
      <p className="text-[11px] text-gray-500 -mt-1">
        {locked ? "The client is locked; documents can't be changed right now."
          : statusLocked ? "The client is with Compliance — you can file the Compliance documents (CDD Form, AML Risk Assessment)." : stage.note}
      </p>

      {/* BRD §14 — prompt for uploads only when it is time: during onboarding, while the folder is empty. */}
      {onboarding && !locked && !uploading && folder.documents.length === 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2">
          <Icon name="warn" size={14} className="text-amber-600" />
          <span className="text-xs text-amber-900 flex-1">No documents yet. Upload the client's KYC and corporate documents before submitting for approval.</span>
          <button onClick={() => setUploading(true)} className="px-2.5 py-1 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Upload now</button>
        </div>
      )}

      {uploading && !locked && (
        <div className="rounded-lg border-2 border-brand-200 bg-brand-50/40 p-3 space-y-2">
          <div className="flex items-center gap-3">
            <div className="text-xs font-semibold text-gray-700">{mode === "link" ? "Add a link" : `Upload a document (max ${folder.max_upload_mb} MB)`}</div>
            <div className="ml-auto flex rounded-lg border border-gray-200 overflow-hidden text-[11px]">
              {[["file", "File"], ["link", "Link (e.g. SharePoint)"]].map(([m, l]) => (
                <button key={m} type="button" onClick={() => setMode(m)} className={`px-2 py-0.5 ${mode === m ? "bg-gray-100 font-semibold text-gray-800" : "bg-white text-gray-500"}`}>{l}</button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select value={category} onChange={(e) => { setCategory(e.target.value); if (cats.items.find((i) => i.code === e.target.value)?.meta?.link_suggested) setMode("link"); }}
              className="border border-gray-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none focus:border-brand-400 max-w-md">
              <option value="">— document category —</option>
              {categoryOptions.map((c) => <option key={c} value={c}>{cats.labelOf(c)}{sectionOf(c) ? ` — ${sectionOf(c)}` : ""}</option>)}
            </select>
            {mode === "file" ? (
              <input ref={fileRef} type="file" accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.bmp"
                className="text-xs file:mr-2 file:py-1 file:px-2 file:rounded file:border file:border-gray-200 file:text-xs file:bg-white" />
            ) : (
              <>
                <input value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="https://…" maxLength={1000}
                  className="flex-1 min-w-[220px] border border-gray-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none focus:border-brand-400" />
                <input value={linkTitle} onChange={(e) => setLinkTitle(e.target.value)} placeholder="Title (optional)" maxLength={255}
                  className="w-48 border border-gray-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none focus:border-brand-400" />
              </>
            )}
          </div>
          {mode === "file" && <p className="text-[10px] text-gray-400">Word, Excel, PDF, JPG, JPEG, PNG or BMP.</p>}
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Note (optional, e.g. certified true copy)" maxLength={500}
            className="w-full border border-gray-200 rounded-lg px-2 py-1 text-xs bg-white focus:outline-none focus:border-brand-400" />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setUploading(false)} className="px-2.5 py-1 text-xs border border-gray-200 rounded-lg bg-white hover:bg-gray-50">Cancel</button>
            <button onClick={upload} disabled={busy} className="px-2.5 py-1 text-xs text-white rounded-lg disabled:opacity-60" style={{ background: "#1a3a5c" }}>
              {busy ? "Saving…" : mode === "link" ? "Add link" : "Upload"}
            </button>
          </div>
        </div>
      )}

      {Object.keys(groups).length === 0 && <p className="text-xs text-gray-400 italic">No documents filed against this client yet.</p>}
      {Object.entries(groups).sort(([a], [b]) => cats.labelOf(a).localeCompare(cats.labelOf(b))).map(([cat, docs]) => {
        const open = openCats[cat] ?? true;
        return (
          <div key={cat} className="rounded-lg bg-gray-50 border border-gray-100">
            <button onClick={() => setOpenCats((o) => ({ ...o, [cat]: !open }))} className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left">
              <Icon name="chevronRight" size={12} className={`text-gray-400 transition-transform ${open ? "rotate-90" : ""}`} />
              <span className="text-xs font-semibold text-gray-700">{cats.labelOf(cat)}</span>
              <span className="text-[10px] text-gray-400">({docs.length})</span>
            </button>
            {open && <div className="px-2.5 pb-2 space-y-1">{docs.map((d) => <Row key={d.id} d={d} />)}</div>}
          </div>
        );
      })}

      {folder.removed?.length > 0 && (
        <details className="rounded-lg border border-gray-100 p-2.5">
          <summary className="text-xs font-semibold text-gray-600 cursor-pointer">Removed documents ({folder.removed.length})</summary>
          <div className="mt-1.5 space-y-1">
            {folder.removed.map((r, i) => (
              <div key={i} className="text-[11px] text-gray-500">
                <span className="line-through">{r.filename}</span> · {cats.labelOf(r.category)} · removed {fmtDate(r.removed_at)}{r.removed_by_name ? ` by ${r.removed_by_name}` : ""}
              </div>
            ))}
          </div>
        </details>
      )}

      {folder.case_documents.length > 0 && (
        <div className="rounded-lg border border-dashed border-gray-200 p-2.5">
          <div className="text-xs font-semibold text-gray-600 mb-1.5">From the client's cases ({folder.case_documents.length}) <span className="font-normal text-gray-400">— managed on each case</span></div>
          <div className="space-y-1">{folder.case_documents.map((d) => <Row key={d.id} d={d} />)}</div>
        </div>
      )}
    </div>
  );
}
