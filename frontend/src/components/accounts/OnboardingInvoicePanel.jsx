import React, { useEffect, useState } from "react";
import { documentsApi, invoicesApi } from "../../api/endpoints";
import { Field, Icon, Select, Textarea } from "../ui";
import MoneyInput from "../MoneyInput";
import { toast } from "../../store/toast";
import { fmtDate } from "../../utils/constants";

const money = (cur, amt) => (amt === null || amt === undefined || amt === "" ? "—" : `${cur || "AED"} ${Number(amt).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);

const YesNoSelect = ({ label, value, onChange, disabled }) => (
  <Field label={label}>
    <Select value={value === true ? "yes" : value === false ? "no" : ""} disabled={disabled}
      onChange={(e) => onChange(e.target.value === "yes" ? true : e.target.value === "no" ? false : null)}>
      <option value="">— select —</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </Select>
  </Field>
);

const fromState = (s) => {
  const inv = s?.invoice;
  return {
    wanted: s?.wanted ?? null,
    client_amount: inv?.amount ?? "", client_currency: inv?.currency || "AED",
    govt_authority_amount: inv?.govt_authority_amount ?? "", govt_authority_currency: inv?.govt_authority_currency || "AED",
    introducer_involved: inv?.introducer_involved ?? null,
    introducer_amount: inv?.introducer_amount ?? "", introducer_currency: inv?.introducer_currency || "AED",
    comments: inv?.notes || "",
  };
};

/**
 * Triam UAT 19-11-2026 (row 153): Invoice for Onboarding Services, after "Is entity regulated". The RM prepares it
 * and submits it to the Accounts Department at any stage of onboarding (Triam 23-11-2026); Accounts answers with the
 * invoice No., date, amount and file and raises it ("Submit to RM"), which shows here. It has its own Save and
 * Submit, so it works while the profile itself is locked for approval.
 */
export default function OnboardingInvoicePanel({ accountId }) {
  const [state, setState] = useState(null);
  const [form, setForm] = useState(fromState(null));
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState([]);

  const apply = (s) => { setState(s); setForm(fromState(s)); };
  useEffect(() => { if (accountId) invoicesApi.onboarding(accountId).then(apply).catch(() => setState(null)); }, [accountId]);
  const raised = state?.invoice && ["Raised", "Paid", "Overdue"].includes(state.invoice.status);
  useEffect(() => {
    if (raised) invoicesApi.attachments(state.invoice.id).then((d) => setFiles(d.filter((x) => x.category === "Invoice"))).catch(() => setFiles([]));
  }, [raised, state?.invoice?.id]);
  if (!accountId) return <p className="text-xs text-gray-500">Save the client first.</p>;
  if (!state) return null;

  const set = (k) => (v) => setForm((p) => ({ ...p, [k]: v }));
  const save = async (submit) => {
    setBusy(true);
    try {
      const num = (v) => (v === "" || v === null || v === undefined ? null : v);
      const next = await invoicesApi.saveOnboarding(accountId, {
        ...form, client_amount: num(form.client_amount), govt_authority_amount: num(form.govt_authority_amount),
        introducer_amount: num(form.introducer_amount), comments: form.comments.trim() || null, submit,
      });
      apply(next);
      toast.success(submit ? "Sent to the Accounts Department" : "Saved");
    } catch (e) { toast.error(e.response?.data?.detail || "Could not save"); } finally { setBusy(false); }
  };

  const inv = state.invoice;
  const off = !state.editable || busy;
  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        <YesNoSelect label="Do you want an invoice raised for onboarding services?" value={form.wanted} onChange={set("wanted")} disabled={off} />
      </div>
      {form.wanted === true && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount payable by the client" required>
              <MoneyInput label="Amount payable by the client" currency={form.client_currency} amount={form.client_amount} disabled={off}
                onCurrency={set("client_currency")} onAmount={set("client_amount")} />
            </Field>
            <Field label="Amount payable to the Regn / Govt Authority">
              <MoneyInput label="Amount payable to the Regn / Govt Authority" currency={form.govt_authority_currency} amount={form.govt_authority_amount}
                disabled={off} onCurrency={set("govt_authority_currency")} onAmount={set("govt_authority_amount")} />
            </Field>
            <YesNoSelect label="Is an introducer / referrer involved?" value={form.introducer_involved} onChange={set("introducer_involved")} disabled={off} />
            {form.introducer_involved === true && (
              <Field label="Amount payable to the introducer" required>
                <MoneyInput label="Amount payable to the introducer" currency={form.introducer_currency} amount={form.introducer_amount}
                  disabled={off} onCurrency={set("introducer_currency")} onAmount={set("introducer_amount")} />
              </Field>
            )}
          </div>
          <Field label="Comments"><Textarea rows={2} value={form.comments} disabled={off} maxLength={2000} onChange={(e) => set("comments")(e.target.value)} /></Field>
        </>
      )}

      {state.editable && (
        <div className="flex flex-wrap items-center gap-2 mt-1">
          <button type="button" onClick={() => save(false)} disabled={busy}
            className="px-3 py-1.5 text-xs rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-50">Save</button>
          {form.wanted === true && (
            <button type="button" onClick={() => save(true)} disabled={busy}
              className="px-3 py-1.5 text-xs rounded-lg border border-brand-600 bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50">
              Submit to Accounts Dept
            </button>
          )}
          {form.wanted === true && state.why_not && <span className="text-[11px] text-gray-500">{state.why_not}</span>}
        </div>
      )}

      {inv && !state.editable && (
        <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-xs text-gray-700">
          <div className="font-semibold text-gray-800 mb-1">
            {raised ? "Accounts Department response" : `With the Accounts Department · ${inv.status}`}
            {inv.requested_at && <span className="font-normal text-gray-500"> · sent {fmtDate(inv.requested_at)}{inv.requested_by_name ? ` by ${inv.requested_by_name}` : ""}</span>}
          </div>
          {raised ? (
            <>
              <div>Invoice No. <span className="font-mono">{inv.invoice_number}</span> · {fmtDate(inv.raised_date)} · {money(inv.currency, inv.amount)}{inv.status === "Paid" ? ` · paid ${fmtDate(inv.paid_date)}` : ""}</div>
              {files.map((d) => (
                <button key={d.id} type="button" onClick={() => documentsApi.download(d.id, d.filename)} className="mt-1 flex items-center gap-1.5 text-brand-600 hover:underline">
                  <Icon name="download" size={12} />{d.filename}
                </button>
              ))}
            </>
          ) : (
            <div>Awaiting the invoice from Accounts. Requested {money(inv.currency, inv.amount)}.</div>
          )}
        </div>
      )}
    </div>
  );
}
