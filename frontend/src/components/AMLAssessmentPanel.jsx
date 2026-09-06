import React, { useEffect, useMemo, useState } from "react";
import { amlApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Icon, Badge, Modal, Field, Input, Select, Textarea } from "./ui";

// ─── Client-side mirror of backend app/services/aml_matrix.calculate ──────────
// Keep in sync with that module. Gives instant preview; server recomputes on save.
function computePreview(catalog, subjectType, selections, countryByName) {
  const defs = subjectType === "Entity" ? catalog.entity_factors : catalog.individual_factors;
  const ratingScore = catalog.rating_score;
  let total = 0;
  const rows = [];
  const overrides = [];
  let blocked = false;
  const missing = [];

  for (const f of defs) {
    const chosen = selections[f.key];
    if (!chosen) missing.push(f.key);
    let rating, score;
    if (f.kind === "country") {
      const cr = countryByName[chosen || ""];
      if (cr) {
        rating = cr.risk_level;
        score = cr.score;
        if (cr.risk_level === "Prohibited") {
          blocked = true;
          overrides.push(`${f.label}: ${chosen} is a prohibited jurisdiction`);
        } else if (cr.default_to_high) {
          overrides.push(`${f.label}: ${chosen} is FATF-listed`);
        }
      } else {
        rating = "High";
        score = 5;
      }
    } else {
      const opt = (f.options || []).find((o) => o.value === chosen);
      rating = opt ? opt.rating : "Medium";
      score = ratingScore[rating] ?? 3;
    }
    const weighted = (score * f.weight) / 100;
    total += weighted;
    rows.push({ ...f, input: chosen, rating, score, weighted_score: weighted });
  }

  total = Math.round(total * 100) / 100;
  let band = "High";
  for (const [lo, hi, label] of catalog.bands) {
    if (total >= lo && total <= hi) { band = label; break; }
  }
  if (selections.pep_risk === catalog.pep_high_option) overrides.push("PEP risk assessed as High");
  const rating = overrides.length ? "High" : band;
  return { rows, total, rating, overrides, blocked, missing };
}

const RatingBadge = ({ rating }) => (rating ? <Badge text={rating} /> : <span className="text-xs text-gray-400">—</span>);

export default function AMLAssessmentPanel({ caseId, entityName, parties = [] }) {
  const user = useAuthStore((s) => s.user);
  const canAssess = ["admin", "screening", "rm"].includes(user?.role);
  const canAmend = ["admin", "screening"].includes(user?.role);
  const canDelete = user?.role === "admin";

  const [catalog, setCatalog] = useState(null);
  const [countries, setCountries] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // "new" | "edit"
  const [form, setForm] = useState(null);

  const countryByName = useMemo(
    () => Object.fromEntries(countries.map((c) => [c.name, c])),
    [countries]
  );

  const load = async () => {
    setLoading(true);
    try {
      const [cat, ctry, list] = await Promise.all([
        amlApi.catalog(),
        amlApi.countryRisk(),
        amlApi.listAssessments(caseId),
      ]);
      setCatalog(cat);
      setCountries(ctry);
      setAssessments(list);
    } catch (e) {
      /* panel is non-critical — fail quietly */
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { if (caseId) load(); }, [caseId]);

  const openNew = () => {
    setForm({
      subject_type: "Entity",
      subject_name: entityName || "",
      director_id: "",
      shareholder_id: "",
      assessment_date: new Date().toISOString().split("T")[0],
      selections: {},
      remarks: "",
      amended_rating: "",
      mlro_notes: "",
    });
    setModal("new");
  };

  const openEdit = (a) => {
    const selections = Object.fromEntries((a.factors || []).filter((r) => r.input).map((r) => [r.key, r.input]));
    setForm({
      id: a.id,
      subject_type: a.subject_type,
      subject_name: a.subject_name,
      director_id: a.director_id || "",
      shareholder_id: a.shareholder_id || "",
      assessment_date: a.assessment_date || "",
      selections,
      remarks: a.remarks || "",
      amended_rating: a.amended_rating || "",
      mlro_notes: a.mlro_notes || "",
    });
    setModal("edit");
  };

  const setSel = (key, value) => setForm((p) => ({ ...p, selections: { ...p.selections, [key]: value } }));

  const preview = useMemo(
    () => (catalog && form ? computePreview(catalog, form.subject_type, form.selections, countryByName) : null),
    [catalog, form, countryByName]
  );

  const save = async () => {
    try {
      if (modal === "new") {
        await amlApi.createAssessment({
          case_id: caseId,
          subject_type: form.subject_type,
          subject_name: form.subject_name,
          director_id: form.director_id ? Number(form.director_id) : null,
          shareholder_id: form.shareholder_id ? Number(form.shareholder_id) : null,
          assessment_date: form.assessment_date || null,
          selections: form.selections,
          remarks: form.remarks || null,
        });
      } else {
        await amlApi.updateAssessment(form.id, {
          subject_name: form.subject_name,
          assessment_date: form.assessment_date || null,
          selections: form.selections,
          remarks: form.remarks || null,
          ...(canAmend && (form.amended_rating || form.mlro_notes)
            ? { amended_rating: form.amended_rating || null, mlro_notes: form.mlro_notes || null }
            : {}),
        });
      }
      setModal(null);
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this AML assessment?")) return;
    try { await amlApi.deleteAssessment(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  if (loading || !catalog) return null;

  const factorDefs = form
    ? (form.subject_type === "Entity" ? catalog.entity_factors : catalog.individual_factors)
    : [];

  return (
    <div className="border-t border-gray-100 pt-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-gray-600">AML Risk Assessment <span className="text-gray-400 font-normal">· matrix v{catalog.version}</span></p>
        {canAssess && (
          <button onClick={openNew} className="px-2.5 py-1 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 flex items-center gap-1">
            <Icon name="plus" size={12} /> New Assessment
          </button>
        )}
      </div>

      {assessments.length === 0 ? (
        <p className="text-xs text-gray-400 italic">No AML risk assessment on file for this entity.</p>
      ) : (
        <div className="space-y-1.5">
          {assessments.map((a) => (
            <div key={a.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
              <div className="min-w-0">
                <div className="text-xs text-gray-700 truncate">
                  <span className="font-medium">{a.subject_name}</span>
                  <span className="text-gray-400"> · {a.subject_type}</span>
                  {a.assessment_date && <span className="text-gray-400"> · {a.assessment_date}</span>}
                </div>
                <div className="text-[11px] text-gray-400">
                  score {a.total_weighted_score ?? "—"}
                  {a.override_reason && <span className="text-amber-600"> · override: {a.override_reason}</span>}
                  {a.onboarding_blocked && <span className="text-red-600 font-medium"> · ONBOARDING BLOCKED</span>}
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                {a.amended_rating
                  ? <span className="flex items-center gap-1"><span className="text-[11px] text-gray-400 line-through">{a.calculated_rating}</span><RatingBadge rating={a.amended_rating} /></span>
                  : <RatingBadge rating={a.calculated_rating} />}
                <button onClick={() => openEdit(a)} className="p-1 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600"><Icon name="edit" size={13} /></button>
                {canDelete && <button onClick={() => remove(a.id)} className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-500"><Icon name="del" size={13} /></button>}
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && form && (
        <Modal title={modal === "new" ? "New AML Risk Assessment" : "AML Risk Assessment"} onClose={() => setModal(null)}>
          <div className="grid grid-cols-2 gap-x-4">
            <Field label="Subject Type" required>
              <Select value={form.subject_type} disabled={modal === "edit"}
                onChange={(e) => setForm((p) => ({ ...p, subject_type: e.target.value, selections: {} }))}>
                <option>Entity</option>
                <option>Individual</option>
              </Select>
            </Field>
            <Field label="Assessment Date">
              <Input type="date" value={form.assessment_date || ""} onChange={(e) => setForm((p) => ({ ...p, assessment_date: e.target.value }))} />
            </Field>
            {form.subject_type === "Individual" && (
              <Field label="Link to Director / Shareholder">
                <Select value={form.director_id ? `d${form.director_id}` : form.shareholder_id ? `s${form.shareholder_id}` : ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    const p = parties.find((x) => `${x._kind[0].toLowerCase()}${x.id}` === v);
                    setForm((f) => ({
                      ...f,
                      director_id: v.startsWith("d") ? Number(v.slice(1)) : "",
                      shareholder_id: v.startsWith("s") ? Number(v.slice(1)) : "",
                      subject_name: p ? p._label : f.subject_name,
                    }));
                  }}>
                  <option value="">— Not linked —</option>
                  {parties.map((p) => {
                    const val = `${p._kind[0].toLowerCase()}${p.id}`;
                    return <option key={val} value={val}>{p._kind} — {p._label}</option>;
                  })}
                </Select>
              </Field>
            )}
            <Field label="Subject Name" required>
              <Input value={form.subject_name} onChange={(e) => setForm((p) => ({ ...p, subject_name: e.target.value }))} />
            </Field>
          </div>

          <div className="mt-1 mb-3 rounded-lg border border-gray-100 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-50 text-gray-500">
                  <th className="text-left py-1.5 px-2 font-medium">Risk Factor</th>
                  <th className="text-left py-1.5 px-2 font-medium">Input</th>
                  <th className="text-right py-1.5 px-2 font-medium w-14">Wt%</th>
                </tr>
              </thead>
              <tbody>
                {factorDefs.map((f) => (
                  <tr key={f.key} className="border-t border-gray-50">
                    <td className="py-1 px-2 text-gray-600">{f.label}</td>
                    <td className="py-1 px-2">
                      <select
                        value={form.selections[f.key] || ""}
                        onChange={(e) => setSel(f.key, e.target.value)}
                        className="w-full border border-gray-200 rounded px-1.5 py-1 text-xs focus:outline-none focus:border-blue-400">
                        <option value="">— select —</option>
                        {f.kind === "country"
                          ? countries.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)
                          : (f.options || []).map((o) => <option key={o.value} value={o.value}>{o.value}</option>)}
                      </select>
                    </td>
                    <td className="py-1 px-2 text-right text-gray-400">{f.weight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {preview && (
            <div className="rounded-lg bg-gray-50 p-3 mb-3 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Preview (server recalculates on save)</span>
                <span className="flex items-center gap-2">
                  <span className="text-gray-500">weighted ≈ {preview.total.toFixed(2)}</span>
                  <RatingBadge rating={preview.rating} />
                </span>
              </div>
              {preview.missing.length > 0 && <div className="text-amber-600">{preview.missing.length} factor(s) not yet selected</div>}
              {preview.overrides.map((o, i) => <div key={i} className="text-amber-700">⚠ {o}</div>)}
              {preview.blocked && <div className="text-red-600 font-semibold">⛔ A prohibited jurisdiction is selected — onboarding blocked.</div>}
            </div>
          )}

          <Field label="Remarks">
            <Textarea value={form.remarks || ""} onChange={(e) => setForm((p) => ({ ...p, remarks: e.target.value }))} />
          </Field>

          {modal === "edit" && canAmend && (
            <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 mb-3">
              <p className="text-xs font-semibold text-amber-800 mb-2">MLRO Amendment (overrides the calculated rating)</p>
              <div className="grid grid-cols-2 gap-x-4">
                <Field label="Amended Rating">
                  <Select value={form.amended_rating || ""} onChange={(e) => setForm((p) => ({ ...p, amended_rating: e.target.value }))}>
                    <option value="">— No amendment —</option>
                    <option>Low</option><option>Medium</option><option>High</option>
                  </Select>
                </Field>
              </div>
              <Field label="MLRO Notes">
                <Textarea value={form.mlro_notes || ""} onChange={(e) => setForm((p) => ({ ...p, mlro_notes: e.target.value }))} />
              </Field>
            </div>
          )}

          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setModal(null)} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
            <button onClick={save} className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#2B6D9A" }}>Save</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
