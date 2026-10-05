import React from "react";
import { Field, Input, Select, Textarea } from "../ui";

export const ACTIVITY_TYPES = ["Visit Report", "Call Report", "Meeting", "Call", "Email", "Follow-up", "Note", "Demo"];
export const REPORT_TYPES = ["Visit Report", "Call Report"];
export const ACTIVITY_STATUSES = ["Planned", "Completed", "Cancelled", "Overdue"];

export const blankActivity = (accountId, type = "Call Report") => ({
  account_id: accountId || "", case_id: "", activity_type: type,
  activity_date: new Date().toISOString().split("T")[0], status: "Completed",
  summary: "", outcome: "", next_action: "", due_date: "",
  client_contact: "", attendees: "", location: "", purpose: "",
});

/** Turns the form into the API payload (empty strings → null, ids → numbers). */
export const activityPayload = (f) => {
  const out = { ...f, account_id: f.account_id ? Number(f.account_id) : null, case_id: f.case_id ? Number(f.case_id) : null };
  ["due_date", "outcome", "next_action", "client_contact", "attendees", "location", "purpose"].forEach((k) => { if (!out[k]) out[k] = null; });
  ["id", "activity_uid", "created_at", "updated_at"].forEach((k) => delete out[k]);
  return out;
};

/** Client-side check matching the server's report rules (BRD §17). */
export const activityProblem = (f) => {
  if (!f.account_id && !f.case_id) return "Choose the client this activity is for";
  if (!f.summary?.trim()) return REPORT_TYPES.includes(f.activity_type) ? "Enter the discussion points" : "Enter a summary";
  if (REPORT_TYPES.includes(f.activity_type) && !f.client_contact?.trim()) return "Enter the client contact";
  if (f.activity_type === "Visit Report" && !f.location?.trim()) return "Enter where the visit took place";
  return null;
};

/**
 * Activity / Visit Report / Call Report form (BRD §17). The client is the anchor; the case is
 * optional and limited to that client's cases. `lockClient` hides the client picker (client screen).
 */
export default function ActivityForm({ form, setForm, accounts = [], cases = [], lockClient = false }) {
  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));
  const isReport = REPORT_TYPES.includes(form.activity_type);
  const clientCases = cases.filter((c) => !form.account_id || c.account_id === Number(form.account_id));

  return (
    <div>
      <div className="grid grid-cols-2 gap-x-4">
        {!lockClient && (
          <Field label="Client" required>
            <Select value={form.account_id || ""} onChange={(e) => setForm((p) => ({ ...p, account_id: e.target.value, case_id: "" }))}>
              <option value="">— choose client —</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.client_id ? `${a.client_id} – ` : ""}{a.company_name}</option>)}
            </Select>
          </Field>
        )}
        <Field label="Case (optional)">
          <Select value={form.case_id || ""} onChange={set("case_id")}>
            <option value="">— none —</option>
            {clientCases.map((c) => <option key={c.id} value={c.id}>{c.case_uid} – {c.company_name}</option>)}
          </Select>
        </Field>
        <Field label="Type" required>
          <Select value={form.activity_type} onChange={set("activity_type")}>
            {ACTIVITY_TYPES.map((t) => <option key={t}>{t}</option>)}
          </Select>
        </Field>
        <Field label="Date" required><Input type="date" value={form.activity_date || ""} onChange={set("activity_date")} /></Field>
        <Field label="Status">
          <Select value={form.status || "Completed"} onChange={set("status")}>
            {ACTIVITY_STATUSES.map((s) => <option key={s}>{s}</option>)}
          </Select>
        </Field>
      </div>

      {isReport && (
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
      )}

      <Field label={isReport ? "Discussion points" : "Summary"} required>
        <Textarea rows={3} value={form.summary || ""} onChange={set("summary")} />
      </Field>
      <Field label="Outcome"><Textarea rows={2} value={form.outcome || ""} onChange={set("outcome")} /></Field>
      <div className="grid grid-cols-2 gap-x-4">
        <Field label="Next action"><Input value={form.next_action || ""} onChange={set("next_action")} /></Field>
        <Field label="Next action due"><Input type="date" value={form.due_date || ""} onChange={set("due_date")} /></Field>
      </div>
    </div>
  );
}
