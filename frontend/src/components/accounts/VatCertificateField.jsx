import React, { useEffect, useRef, useState } from "react";
import { documentsApi } from "../../api/endpoints";
import { Icon } from "../ui";
import { toast } from "../../store/toast";
import { fmtDate } from "../../utils/constants";

const VAT_CERT = "VAT_CERT"; // "VAT Registration Certificate" in the Document Categories master

/** Triam 13-11-2026: the VAT Certificate is uploaded where the RM types the VAT number. It is filed in the
 *  client's folder like any other document (same size limit, stages and history). */
export default function VatCertificateField({ accountId, disabled = false, onChange }) {
  const [docs, setDocs] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const load = () => (accountId
    ? documentsApi.listForAccount(accountId).then((all) => setDocs((all || []).filter((d) => d.category === VAT_CERT && !d.removed_at))).catch(() => setDocs([]))
    : setDocs([]));
  useEffect(() => { load(); }, [accountId]); // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", VAT_CERT);
      await documentsApi.uploadForAccount(accountId, fd);
      toast.success("VAT Certificate uploaded to the client folder");
      await load();
      onChange?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (!accountId) return <p className="text-[11px] text-gray-400 mt-2">Save the client first to upload the VAT Certificate.</p>;
  return (
    <div className="mt-2">
      {(docs || []).map((d) => (
        <button key={d.id} type="button" onClick={() => documentsApi.download(d.id, d.filename)}
          className="flex items-center gap-1.5 text-xs text-brand-600 hover:underline">
          <Icon name="download" size={12} />{d.filename}<span className="text-gray-400">· {fmtDate(d.created_at)}</span>
        </button>
      ))}
      {!disabled && (
        <label className={`inline-flex items-center gap-1.5 mt-1 px-2.5 py-1 text-xs border border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-brand-300 hover:text-brand-600 text-gray-600 ${busy ? "opacity-60 pointer-events-none" : ""}`}>
          <Icon name="plus" size={13} /> {busy ? "Uploading…" : (docs || []).length ? "Upload a newer VAT Certificate" : "Upload VAT Certificate"}
          <input ref={fileRef} type="file" aria-label="Upload VAT Certificate" className="hidden"
            accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.bmp" onChange={(e) => upload(e.target.files[0])} />
        </label>
      )}
    </div>
  );
}
