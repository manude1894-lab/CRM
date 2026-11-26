import React from "react";
import { Field, Input, Select, Textarea, DateInput } from "../ui";
import ClientPicker from "../ClientPicker";

export const ACTIVITY_TYPES = ["Visit Report", "Call Report"];
// Triam 23-11-2026: a report is a Draft until "Save the Report" makes it final (status Completed).
export const isFinal = (a) => a?.status === "Completed";
export const isEditable = (a) => !a?.id || ["Draft", "Planned", "Overdue"].includes(a.status);

export const blankActivity = (accountId, type = "Call Report") => ({
  account_id: accountId || "", activity_type: type,
  activity_date: new Date().toISOString().split("T")[0],
  summary: "", outcome: "", next_action: "", due_date: "",
  client_contact: "", attendees: "", location: "", purpose: "",
});

/** Turns the form into the API payload (empty strings → null, ids → numbers). */
export const activityPayload = (f) => {
  const out = { ...f, account_id: f.account_id ? Number(f.account_id) : null };
  ["due_date", "outcome", "next_action", "client_contact", "attendees", "location", "purpose"].forEach((k) => { if (!out[k]) out[k] = null; });
  ["id", "activity_uid", "created_at", "updated_at", "status", "cancel_reason", "owner_name", "finalised_at",
    "finalised_by_name", "corrections"].forEach((k) => delete out[k]);
  return out;
};

/** "Save Draft" needs only the client; the rest can be finished later. */
export const draftProblem = (f) => (f.account_id ? null : "Choose the client this report is for");

/** "Save the Report": the server's rules for the final report (BRD §15). */
export const activityProblem = (f) => {
  if (!f.account_id) return "Choose the client this report is for";
  if (!f.summary?.trim()) return "Enter the discussion points";
  if (!f.client_contact?.trim()) return "Enter the client contact";
  if (f.activity_type === "Visit Report" && !f.location?.trim()) return "Enter where the visit took place";
  return null;
};

/**
 * Visit Report / Call Report form (BRD §15), always on a client. `lockClient` hides the client picker
 * (client screen).
 */
export default function ActivityForm({ form, setForm, accounts = [], lockClient = false }) {
  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div>
      <div className="grid grid-cols-2 gap-x-4">
        {!lockClient && (
          <Field label="Client" required>
            <ClientPicker clients={accounts} value={form.account_id || ""} onChange={(v) => setForm((p) => ({ ...p, account_id: v }))} />
          </Field>
        )}
        <Field label="Type" required>
          <Select value={form.activity_type} onChange={set("activity_type")}>
            {ACTIVITY_TYPES.map((t) => <option key={t}>{t}</option>)}
          </Select>
        </Field>
        <Field label="Date" required><DateInput value={form.activity_date || ""} onChange={set("activity_date")} /></Field>
      </div>

      <div className="rounded-lg border border-brand-100 bg-brand-50/30 px-3 pt-3 mb-3">
        <div className="text-[11px] font-semibold text-brand-700 uppercase tracking-wide mb-2">{form.activity_type}</div>
        <div className="grid grid-cols-2 gap-x-4">
          <Field label={form.activity_type === "Visit Report" ? "Client contact met" : "Client contact spoken to"} required>
            <Input value={form.client_contact || ""} onChange={set("client_contact")} maxLength={150} placeholder="Name and designation" />
          </Field>
          {form.activity_type === "Visit Report" && (
            <Field label="Location" required><Input value={form.location || ""} onChange={set("location")} maxLength={200} placeholder="e.g. Client office, JLT" /></Field>
          )}
          <Field label="Triam attendees"><Input value={form.attendees || ""} onChange={set("attendees")} placeholder="e.g. Rita (RM), Carl (CO)" /></Field>
          <Field label="Purpose"><Input value={form.purpose || ""} onChange={set("purpose")} maxLength={200} placeholder="e.g. Annual relationship review" /></Field>
        </div>
      </div>

      <Field label="Discussion points" required>
        <Textarea rows={3} value={form.summary || ""} onChange={set("summary")} />
      </Field>
      <Field label="Outcome"><Textarea rows={2} value={form.outcome || ""} onChange={set("outcome")} /></Field>
      <div className="grid grid-cols-2 gap-x-4">
        <Field label="Next action"><Input value={form.next_action || ""} onChange={set("next_action")} /></Field>
        <Field label="Next action due"><DateInput min={new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Dubai" })} value={form.due_date || ""} onChange={set("due_date")} /></Field>
      </div>
    </div>
  );
}
