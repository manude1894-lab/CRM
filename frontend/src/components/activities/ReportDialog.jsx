import React, { useState } from "react";
import { activitiesApi } from "../../api/endpoints";
import { Button, Field, Modal, Textarea } from "../ui";
import { toast } from "../../store/toast";
import { fmtDate } from "../../utils/constants";
import ActivityForm, { activityPayload, activityProblem, draftProblem, isEditable } from "./ActivityForm";
import ActivityCard from "./ActivityCard";

/**
 * A Visit / Call Report (Triam 23-11-2026, S T Krishna). While it is a draft: Cancel, Save Draft, Save the Report.
 * Once saved it is final: shown as written, with any correction notes, and a note can be added.
 */
export default function ReportDialog({ report, accounts = [], lockClient = false, readOnly = false, onClose, onSaved }) {
  const [form, setForm] = useState(report);
  const [busy, setBusy] = useState(null);
  const [note, setNote] = useState("");
  const editable = !readOnly && isEditable(report);
  const title = report.id ? `${report.activity_type} ${report.activity_uid}` : `New ${report.activity_type}`;

  const save = async (final) => {
    const problem = final ? activityProblem(form) : draftProblem(form);
    if (problem) return toast.error(problem);
    setBusy(final ? "final" : "draft");
    try {
      const payload = { ...activityPayload(form), final };
      if (report.id) await activitiesApi.update(report.id, payload); else await activitiesApi.create(payload);
      toast.success(final ? `${form.activity_type} saved` : "Draft saved. Finish it and Save the Report when ready");
      onSaved();
    } catch (e) { toast.error(e.response?.data?.detail || "Save failed"); } finally { setBusy(null); }
  };
  const addNote = async () => {
    if (note.trim().length < 2) return toast.error("Write the correction");
    setBusy("note");
    try { await activitiesApi.correct(report.id, note.trim()); toast.success("Correction added"); onSaved(); }
    catch (e) { toast.error(e.response?.data?.detail || "Could not add the correction"); } finally { setBusy(null); }
  };

  if (!editable) {
    return (
      <Modal title={title} onClose={onClose}>
        <ActivityCard activity={report} />
        {report.finalised_at && (
          <p className="text-xs text-gray-500 mt-2">Saved as the final report {fmtDate(report.finalised_at)}{report.finalised_by_name ? ` by ${report.finalised_by_name}` : ""}. It is kept as written.</p>
        )}
        {!readOnly && report.status === "Completed" && (
          <div className="mt-3 pt-3 border-t border-gray-100">
            <Field label="Add a correction note"><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000}
              placeholder="What was wrong or missing; the report itself stays as written" /></Field>
          </div>
        )}
        <div className="flex justify-end gap-2 mt-3">
          <Button onClick={onClose}>Close</Button>
          {!readOnly && report.status === "Completed" && <Button variant="primary" onClick={addNote} disabled={!!busy}>{busy === "note" ? "Adding…" : "Add correction"}</Button>}
        </div>
      </Modal>
    );
  }
  return (
    <Modal title={title} onClose={onClose}>
      <ActivityForm form={form} setForm={setForm} accounts={accounts} lockClient={lockClient} />
      <div className="flex justify-end gap-2 mt-2 pt-3 border-t border-gray-100">
        <Button onClick={onClose} disabled={!!busy}>Cancel</Button>
        <Button onClick={() => save(false)} disabled={!!busy}>{busy === "draft" ? "Saving…" : "Save Draft"}</Button>
        <Button variant="primary" onClick={() => save(true)} disabled={!!busy}>{busy === "final" ? "Saving…" : "Save the Report"}</Button>
      </div>
    </Modal>
  );
}
