import React, { useEffect, useRef, useState } from "react";
import { documentsApi } from "../../api/endpoints";
import { Button, Icon, Spinner } from "../ui";
import { IMAGE_MIME, ext, neutralizeDocument, previewKind } from "../../utils/preview";

// The file is fetched with the user's sign-in and shown here; the bytes are typed by the CRM (never by the
// upload), so a file can only be shown as a PDF, a picture, text or a Word document. A Word document is drawn
// without its embedded HTML parts, and its links are cleaned, so nothing in an uploaded file can run.
export default function DocumentPreview({ doc, onClose }) {
  const kind = previewKind(doc.content_type, doc.filename);
  const [url, setUrl] = useState(null);
  const [text, setText] = useState(null);
  const [loading, setLoading] = useState(!!kind);
  const [failed, setFailed] = useState(false);
  const docxRef = useRef(null);

  useEffect(() => {
    let objectUrl = null;
    let cancelled = false;
    (async () => {
      if (!kind) return;
      try {
        const data = await documentsApi.content(doc.id);
        if (cancelled) return;
        if (kind === "text") setText(await data.text());
        else if (kind === "docx") {
          const { renderAsync } = await import("docx-preview");
          if (cancelled) return;
          setLoading(false);
          await renderAsync(data, docxRef.current, undefined,
            { inWrapper: true, ignoreLastRenderedPageBreak: true, renderAltChunks: false, renderComments: false });
          if (!cancelled && docxRef.current) neutralizeDocument(docxRef.current);
        } else {
          const e = ext(doc.filename);
          const type = kind === "pdf" ? "application/pdf" : IMAGE_MIME.test(data.type) ? data.type : `image/${e === "jpg" ? "jpeg" : e}`;
          objectUrl = URL.createObjectURL(new Blob([data], { type }));
          setUrl(objectUrl);
        }
      } catch {
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [doc.id]);

  const download = () => documentsApi.download(doc.id, doc.filename);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-2 sm:p-6" style={{ background: "rgba(0,0,0,0.55)" }} onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl h-full max-h-[92vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-800 truncate flex-1" title={doc.filename}>{doc.filename}</h2>
          <button onClick={download}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">
            <Icon name="download" size={13} /> Download
          </button>
          <button onClick={onClose} title="Close" className="text-gray-400 hover:text-gray-600"><Icon name="close" size={20} /></button>
        </div>
        <div className="flex-1 min-h-0 bg-gray-100 overflow-auto">
          {loading && <div className="h-full flex items-center justify-center"><Spinner /></div>}
          {!loading && (failed || !kind) && (
            <div className="h-full flex flex-col items-center justify-center gap-3 text-sm text-gray-500 p-6 text-center">
              {failed ? "The document could not be opened." : "Preview is not available for this file type."}
              <Button variant="primary" onClick={download}>Download</Button>
            </div>
          )}
          {kind === "pdf" && url && <iframe src={url} title={doc.filename} className="w-full h-full border-0 bg-white" />}
          {kind === "image" && url && (
            <div className="min-h-full flex items-center justify-center p-4"><img src={url} alt={doc.filename} className="max-w-full max-h-full object-contain shadow" /></div>
          )}
          {kind === "text" && text !== null && (
            <pre className="m-4 p-4 bg-white rounded-lg text-xs text-gray-800 whitespace-pre-wrap break-words">{text}</pre>
          )}
          {kind === "docx" && !failed && <div ref={docxRef} className="docx-preview" />}
        </div>
      </div>
    </div>
  );
}
