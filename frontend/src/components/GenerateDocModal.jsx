import React, { useEffect, useState } from "react";
import { generationApi, documentsApi } from "../api/endpoints";
import { Modal, Field, Input, Select, Textarea, Spinner } from "./ui";

export default function GenerateDocModal({ caseId, onClose }) {
  const [templates, setTemplates] = useState([]);
  const [code, setCode] = useState("");
  const [fields, setFields] = useState([]);
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    generationApi.templates()
      .then((t) => { setTemplates(t || []); setLoading(false); })
      .catch(() => { setTemplates([]); setLoading(false); });
  }, []);

  const pick = async (c) => {
    setCode(c);
    const tpl = templates.find((t) => t.code === c);
    setFields(tpl?.fields || []);
    setForm({});
    if (!c) return;
    try {
      const pf = await generationApi.prefill(caseId, c);
      setForm(pf || {});
    } catch { /* keep empty */ }
  };

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const missing = fields.filter((f) => f.required && !String(form[f.key] || "").trim());

  const generate = async () => {
    if (!code || missing.length) return;
    setBusy(true);
    try {
      const doc = await generationApi.generate(caseId, { template_code: code, params: form });
      await documentsApi.download(doc.id, doc.filename);
      onClose(true);
    } catch (e) {
      alert(e.response?.data?.detail || "Generation failed");
    } finally { setBusy(false); }
  };

  return (
    <Modal title="Generate Document" onClose={() => onClose(false)}>
      {loading ? <Spinner /> : (
        <div className="space-y-3">
          <Field label="Template">
            <Select value={code} onChange={(e) => pick(e.target.value)}>
              <option value="">— select a template —</option>
              {templates.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
            </Select>
          </Field>

          {code && fields.map((f) => (
            <Field key={f.key} label={f.label + (f.required ? " *" : "")}>
              {f.type === "textarea" ? (
                <Textarea value={form[f.key] || ""} onChange={set(f.key)} />
              ) : f.type === "select" ? (
                <Select value={form[f.key] || ""} onChange={set(f.key)}>
                  <option value="">— select —</option>
                  {(f.options || []).map((o) => <option key={o}>{o}</option>)}
                </Select>
              ) : (
                <Input type={f.type === "date" ? "date" : "text"} value={form[f.key] || ""} onChange={set(f.key)} />
              )}
            </Field>
          ))}

          {code && (
            <p className="text-[11px] text-gray-400">
              The document is rendered as a PDF, downloaded, and attached to this case.
            </p>
          )}

          <div className="flex justify-end gap-3 pt-1">
            <button onClick={() => onClose(false)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={generate} disabled={!code || busy || missing.length > 0}
              className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50" style={{ background: "#2B6D9A" }}>
              {busy ? "Generating…" : "Generate & Attach"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
