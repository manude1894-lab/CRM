import React, { useEffect, useRef, useState } from "react";
import { accountsApi, workflowApi } from "../../api/endpoints";
import { Icon, Modal, Field, Input, Select, MultiSelect, CountrySelect, Textarea, DateInput, Embedded, PassportNote } from "../ui";
import AccountPartyModal from "../AccountPartyModal";
import NameLookup from "./NameLookup";
import CompletenessChecklist from "./CompletenessChecklist";
import WorkflowBar from "./WorkflowBar";
import AmendmentBar from "./AmendmentBar";
import ClientDocumentsFolder from "./ClientDocumentsFolder";
import { useAuthStore } from "../../store/auth";
import { MONTHS, parseFYE, toFYE, fmtFYE, daysIn } from "../../utils/fye";
import { toast } from "../../store/toast";
import { confirmDialog } from "../../store/confirm";
import {
  fmtDate, REGULATOR_OPTIONS, TAG_OPTIONS, SERVICES_OBTAINED_OPTIONS,
  COUNTRY_CALLING_CODES, TRIAM_ENTITY_OPTIONS, isUAE, isRelationshipManager, personLabel,
  WITH_RM_STATUSES,
} from "../../utils/constants";
import {
  RISK_OPTIONS, BLANK_ADDRESS, SECTION_FIELDS,
  buildAccountPayload, buildSectionPatch, validateCoreFields, accountToForm, mandatoryFields, isOffshore, sameAddress, isFoundation, withServicesSought, clientMobileProblem,
} from "./accountForm";
import { dialCodeForCountry, dialCodeOptions } from "../../utils/dialCodes";
import MobileNumberInput from "../MobileNumberInput";
import { useMasters } from "../../hooks/useMasters";
import { selectableCodes, servicesForEntities } from "../../hooks/masterUtils";

// Service lists are shown in alphabetical order (Triam UAT 26-10-2026).
const alphabetical = (codes) => [...codes].sort((x, y) => x.localeCompare(y));

// readOnly: the client is locked (submitted, approved without an amendment, exited) — fields are shown, not editable.
const Section = ({ title, children, hasData, onSave, status, error, dirty, readOnly = false }) => {
  const [open, setOpen] = useState(!!hasData);
  return (
    <div className="mb-2 border border-gray-100 rounded-lg overflow-hidden">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
          {title}
          {hasData && <span className="w-1.5 h-1.5 rounded-full bg-brand-500 flex-shrink-0" />}
          {onSave && dirty && <span className="normal-case tracking-normal text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">Unsaved changes</span>}
        </span>
        <Icon name="chevronRight" size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="px-3 py-3">
          {readOnly ? <fieldset disabled className="min-w-0">{children}</fieldset> : children}
          {onSave && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
              <button type="button" onClick={onSave} disabled={status === "saving" || dirty === false} title={dirty === false ? "No changes to save" : ""}
                className={`px-3 py-1.5 text-xs rounded-lg border disabled:cursor-not-allowed ${dirty !== false
                  ? "border-brand-600 bg-brand-600 text-white hover:bg-brand-700" : "border-gray-200 text-gray-400 bg-white"}`}>
                {status === "saving" ? "Saving…" : `Save ${title}`}
              </button>
              {status === "saved" && <span className="text-xs text-emerald-600">Saved</span>}
              {status === "error" && <span className="text-xs text-red-600">{error || "Save failed"}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// BRD §5 "Mandatory Yes/No": blank until answered, so an unanswered question is not taken as "No".
const YesNo = ({ label, value, onChange, required }) => (
  <Field label={label} required={required}>
    <Select value={value === true ? "yes" : value === false ? "no" : ""} onChange={(e) => onChange(e.target.value === "yes" ? true : e.target.value === "no" ? false : null)}>
      <option value="">— select —</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </Select>
  </Field>
);

const AddressFields = ({ value, onChange, countries, required }) => {
  const v = value || BLANK_ADDRESS;
  const set = (k) => (e) => onChange({ ...v, [k]: e.target.value });
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Address Line 1" required={required}><Input value={v.line1 || ""} onChange={set("line1")} /></Field>
      <Field label="Address Line 2"><Input value={v.line2 || ""} onChange={set("line2")} /></Field>
      <Field label="Landmark"><Input value={v.landmark || ""} onChange={set("landmark")} /></Field>
      <Field label="City" required={required}><Input value={v.city || ""} onChange={set("city")} /></Field>
      <Field label="ZIP Code"><Input value={v.zip || ""} onChange={set("zip")} /></Field>
      <Field label="P.O. Box No."><Input value={v.po_box || ""} onChange={set("po_box")} /></Field>
      <Field label="Country" required={required}><CountrySelect value={v.country || ""} onChange={set("country")} countries={countries} /></Field>
    </div>
  );
};

/**
 * New / Edit Client modal. Owns its form state; the parent remounts it (via `key`) to open a different client.
 * - onChanged: called after any successful save so the parent can reload the list.
 * - onOpenExisting(account): user picked an existing client from the duplicate warning.
 */
export default function AccountFormModal({ initialForm, users, countries, onClose, onChanged, onOpenExisting, hideWorkflow = false }) {
  const [form, setForm] = useState(initialForm);
  // What the server last saved — a section's Save is active only when it differs (unsaved changes).
  const [saved, setSaved] = useState(initialForm);
  const loadForm = (f) => { setForm(f); setSaved(f); };
  const sectionDirty = (key) => JSON.stringify(buildSectionPatch(form, SECTION_FIELDS[key])) !== JSON.stringify(buildSectionPatch(saved, SECTION_FIELDS[key]));
  const anyDirty = Object.keys(SECTION_FIELDS).some(sectionDirty);
  const [mode, setMode] = useState(initialForm._id ? "edit" : "new");
  const [saving, setSaving] = useState(false);
  const [sectionStatus, setSectionStatus] = useState({});
  const [sectionError, setSectionError] = useState({});
  // BRD §3 — exact-name duplicate and the approver exception.
  const [exactMatch, setExactMatch] = useState(false);
  const [override, setOverride] = useState({ allow: false, reason: "" });
  const [refreshKey, setRefreshKey] = useState(0);
  // BRD §13 — an approved client is changed only through an amendment that Compliance approves.
  const [amendment, setAmendment] = useState(null);
  const [previewOf, setPreviewOf] = useState(null); // request id whose staged values are loaded in the form
  const approvedClient = ["Approved", "Active", "Inactive", "Marked for Exit"].includes(form.profile_status);
  const myDraft = amendment?.request?.status === "Draft" && amendment.actions.includes("submit");
  const amendLocked = !!form._id && approvedClient && !myDraft;
  const readOnlyUser = useAuthStore((s) => s.isReadOnly());
  // The asterisks follow one rule, tested against the server's rule (backend/tests/contracts/mandatory_fields.json).
  const mandatory = mandatoryFields(form);
  const req = (field) => mandatory.has(field);
  const offshore = form.account_type !== "Individual" && isOffshore(form);
  const showVat = !offshore || !!form.trn_vat_number;
  const showCorpTax = !offshore || form.corp_tax_registered === true || !!form.corp_tax_registration_number;
  const locked = readOnlyUser || ["Awaiting Approval", "Exited"].includes(form.profile_status) || amendLocked;
  // BRD §7/§11: only Compliance completes the CDD section — before submission, while the
  // client is with Compliance, or in an amendment of an approved client.
  const canCdd = useAuthStore((st) => st.can("client.cdd_edit"));
  const [stage, setStage] = useState(null);
  useEffect(() => {
    if (form._id && form.profile_status === "Awaiting Approval") workflowApi.get(form._id).then((w) => setStage(w.stage)).catch(() => setStage(null));
    else setStage(null);
  }, [form._id, form.profile_status, refreshKey]);
  const cddEditable = canCdd && (!locked || (form.profile_status === "Awaiting Approval" && stage === "Compliance"));
  // Footer Submit: save, then open the submit dialog of the client workflow or of the draft amendment.
  // The form closes once the client / amendment has gone to Compliance.
  const [wfSubmit, setWfSubmit] = useState(null); // the workflow's "submit" action for this user, if any
  const [submitSignal, setSubmitSignal] = useState(0);
  const [amendSubmitSignal, setAmendSubmitSignal] = useState(0);
  const footerSubmit = useRef(false);
  const onWorkflowState = (s) => setWfSubmit(s?.actions.find((a) => a.action === "submit") || null);
  const onAmendmentState = (s) => {
    setAmendment(s);
    if (footerSubmit.current && s?.request && s.request.status !== "Draft") { footerSubmit.current = false; onChanged(); onClose(); return; }
    // Show the maker their staged values (once per draft; later saves keep the form as typed).
    if (s?.preview && s.request && previewOf !== s.request.id) {
      setPreviewOf(s.request.id);
      loadForm(accountToForm(s.preview.account));
    }
  };
  const onAmendmentDecided = async () => {
    // After approve / discard / withdraw, reload the live client so the form shows what is current.
    setPreviewOf(null);
    try { loadForm(accountToForm(await accountsApi.get(form._id))); } catch { /* keep the form as it is */ }
    setRefreshKey((k) => k + 1);
    onChanged();
  };
  const onWorkflowChanged = (state) => {
    if (footerSubmit.current && state.status === "Awaiting Approval") { footerSubmit.current = false; onChanged(); onClose(); return; }
    setForm((f) => ({ ...f, profile_status: state.status, _status_updated_at: state.status_updated_at }));
    setRefreshKey((k) => k + 1);
    onChanged();
  };
  const canApprove = useAuthStore((s) => s.can("client.approve"));
  const canFinalApprove = useAuthStore((s) => s.can("client.final_approve"));
  const showCdd = canCdd || canApprove || canFinalApprove;
  // High-risk countries linked to the client and its parties, shown beside the CDD/AML risk level.
  const [riskLinks, setRiskLinks] = useState([]);
  useEffect(() => {
    let current = true;
    setRiskLinks([]);
    if (showCdd && form._id) accountsApi.countryRisk(form._id).then((links) => current && setRiskLinks(links)).catch(() => {});
    return () => { current = false; };
  }, [showCdd, form._id, refreshKey]);

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const setChecked = (key) => (e) => setForm({ ...form, [key]: e.target.checked });
  const setValue = (key) => (v) => setForm({ ...form, [key]: v });
  // Triam UAT 05-11-2026: choosing the country fills the Contact Mobile code; it can still be changed.
  const isdFor = (country, field) => { const code = dialCodeForCountry(country, countries); return code ? { [field]: code } : {}; };
  const dialOptions = dialCodeOptions(countries, COUNTRY_CALLING_CODES);
  const setOperatingAddress = (v) => setForm({ ...form, operating_address: v,
    ...(v.country !== form.operating_address?.country ? isdFor(v.country, "contact_mobile_country_code") : {}) });
  // Triam UAT 05-11-2026: the Operating Address can follow the Registered Address, and keeps following it
  // while ticked. Starts ticked when the two are already the same.
  const [sameAsRegistered, setSameAsRegistered] = useState(() => sameAddress(initialForm.registered_address, initialForm.operating_address));
  const setRegisteredAddress = (v) => setForm({ ...form, registered_address: v,
    ...(sameAsRegistered ? { operating_address: { ...v }, ...(v.country !== form.operating_address?.country ? isdFor(v.country, "contact_mobile_country_code") : {}) } : {}) });
  const toggleSameAsRegistered = (e) => {
    setSameAsRegistered(e.target.checked);
    if (e.target.checked) setOperatingAddress({ ...form.registered_address });
  };
  const rms = users.filter((u) => isRelationshipManager(u) || u.id === +form.spoc_id || (form.non_anchor_rm_ids || []).includes(u.id));
  const isIndividual = form.account_type === "Individual";
  // BRD §18 — admin-managed lists; the old constants are the fallback until the API answers.
  const entities = useMasters("triam_entity", TRIAM_ENTITY_OPTIONS);
  const services = useMasters("service", SERVICES_OBTAINED_OPTIONS);
  // Services the client's Triam entities offer: what Services obtained may hold.
  const obtainableServices = selectableCodes(servicesForEntities(services.items, [form.anchor_entity, ...(form.non_anchor_entities || [])]), form.services_obtained);
  const setServicesSought = (v) => setForm(withServicesSought(form, v, obtainableServices));
  const tags = useMasters("tag", TAG_OPTIONS);
  const regulators = useMasters("regulator", REGULATOR_OPTIONS);
  const authorities = useMasters("licensing_authority", []);

  const setCompanyName = (e) => {
    const value = e.target.value;
    setForm((f) => ({ ...f, company_name: value }));
  };

  // Create payload extras + the duplicate gate (BRD §3).
  const duplicateBlock = () => {
    if (!exactMatch) return null;
    if (!canApprove) return "A client with this exact name already exists. Open it instead, or ask an approver to create a duplicate.";
    if (!override.allow) return "A client with this exact name already exists. Tick 'Create anyway' and give a reason to continue.";
    if ((override.reason || "").trim().length < 10) return "Give a meaningful reason (at least 10 characters) for creating a duplicate client.";
    return null;
  };
  const withOverride = (payload) => (exactMatch && override.allow ? { ...payload, allow_duplicate: true, duplicate_reason: override.reason.trim() } : payload);

  // Saves the whole form; true when saved. A new client becomes an edited one (the form stays open).
  const persist = async () => {
    // The core rules (name, Anchor Triam Entity, duplicates) are checked when creating a client.
    const invalid = clientMobileProblem(form)
      || (mode === "new" ? (validateCoreFields(form) || duplicateBlock()) : (!form.company_name?.trim() && "Company name is required"));
    if (invalid) { toast.error(invalid); return false; }
    try {
      setSaving(true);
      const payload = buildAccountPayload(form);
      if (mode === "edit") {
        const updated = await accountsApi.update(form._id, payload);
        setForm((f) => ({ ...f, next_aml_review_date: updated.next_aml_review_date, _client_id: updated.client_id || f._client_id }));
      } else {
        const created = await accountsApi.create(withOverride({ ...payload, prospect_id: form.prospect_id || null }));
        setForm((f) => ({ ...f, _id: created.id, search_name: created.search_name, _client_id: created.client_id, _status_updated_at: created.status_updated_at }));
        setMode("edit");
      }
      setSaved(form);
      setRefreshKey((k) => k + 1);
      onChanged();
      return true;
    } catch (e) {
      toast.error(e.response?.data?.detail || (mode === "edit" ? "Failed to update client" : "Failed to create client"));
      return false;
    } finally { setSaving(false); }
  };
  // Save: keep it as a draft (New / WIP, or the open amendment) and close.
  const save = async () => { if (await persist()) onClose(); };
  // Submit: save what is unsaved, then the submit dialog (comments, KYC declaration) sends it to Compliance.
  const submit = async () => {
    if ((mode === "new" || anyDirty) && !(await persist())) return;
    footerSubmit.current = true;
    if (myDraft) setAmendSubmitSignal((n) => n + 1);
    else setSubmitSignal((n) => n + 1);
  };
  // Cancel: close without saving; asks first when something is unsaved.
  const cancel = async () => {
    if (anyDirty && !(await confirmDialog({ title: "Discard changes?", message: "The changes you haven't saved will be lost.", confirmLabel: "Discard", danger: true }))) return;
    onClose();
  };
  const canSubmit = !locked && (myDraft || (!approvedClient && (mode === "new" || !!wfSubmit)));

  // BRD §10 — per-section Save, so each section validates and
  // persists independently instead of only surfacing errors at the very bottom of the form.
  const saveSection = async (key, isCore = false) => {
    setSectionStatus((s) => ({ ...s, [key]: "saving" }));
    setSectionError((s) => ({ ...s, [key]: null }));
    const snapshot = form;
    try {
      const mobileError = clientMobileProblem(form);
      if (mobileError) throw new Error(mobileError);
      const patch = buildSectionPatch(form, SECTION_FIELDS[key]);
      if (form._id) {
        const updated = await accountsApi.update(form._id, patch);
        setForm((f) => ({ ...f, next_aml_review_date: updated.next_aml_review_date, search_name: updated.search_name || f.search_name,
          _client_id: updated.client_id || f._client_id, _status_updated_at: updated.status_updated_at }));
      } else {
        if (!isCore) throw new Error("Save Client Info first.");
        const invalid = validateCoreFields(form) || duplicateBlock();
        if (invalid) throw new Error(invalid);
        const created = await accountsApi.create(withOverride({ ...patch, prospect_id: form.prospect_id || null }));
        setForm((f) => ({ ...f, _id: created.id, search_name: created.search_name, _client_id: created.client_id, _status_updated_at: created.status_updated_at }));
        setMode("edit");
      }
      setSaved((prev) => ({ ...prev, ...Object.fromEntries(SECTION_FIELDS[key].map((f) => [f, snapshot[f]])) }));
      setSectionStatus((s) => ({ ...s, [key]: "saved" }));
      setRefreshKey((k) => k + 1);
      onChanged();
      setTimeout(() => setSectionStatus((s) => (s[key] === "saved" ? { ...s, [key]: "idle" } : s)), 2500);
    } catch (e) {
      setSectionStatus((s) => ({ ...s, [key]: "error" }));
      setSectionError((s) => ({ ...s, [key]: e.response?.data?.detail || e.message || "Save failed" }));
    }
  };

  const sectionProps = (key) => ({ onSave: locked ? undefined : () => saveSection(key), readOnly: locked, status: sectionStatus[key], error: sectionError[key], dirty: sectionDirty(key) });
  const today = new Date().toISOString().slice(0, 10);

  return (
    <Modal title={mode === "edit" ? "Edit Client" : "New Client"} onClose={cancel}>
      <div className="space-y-3">
        {form._id && !hideWorkflow && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs text-gray-600">
            <span>Client ID <span className="font-mono font-semibold text-gray-800">{form._client_id || "—"}</span></span>
            {form._status_updated_at && <span>Status last updated {fmtDate(form._status_updated_at)}</span>}
          </div>
        )}
        {form._id && <WorkflowBar accountId={form._id} refreshKey={refreshKey} onChanged={onWorkflowChanged}
          onState={onWorkflowState} submitSignal={submitSignal} dialogOnly={hideWorkflow} />}
        {form._id && approvedClient && (
          <AmendmentBar accountId={form._id} refreshKey={refreshKey} onState={onAmendmentState} onDecided={onAmendmentDecided} submitSignal={amendSubmitSignal} />
        )}
        {!locked && !approvedClient && <CompletenessChecklist accountId={form._id} refreshKey={refreshKey} />}
        {mode === "new" && form._prospect_uid && (
          <div className="mb-3 text-xs rounded-lg bg-brand-50 text-brand-700 px-3 py-2">
            Creating the client from prospect <span className="font-mono font-semibold">{form._prospect_uid}</span>. This is the client's
            temporary ID until Compliance approves it and the Client ID is issued.
          </div>
        )}
        <fieldset disabled={locked} className="min-w-0">
        <Field label="Client Type">
          <Select value={form.account_type} onChange={set("account_type")}>
            <option>Corporate</option>
            <option>Individual</option>
          </Select>
        </Field>
        <Field label={isIndividual ? "Full Name (as per passport)" : "Company Name"} required={req("company_name")}>
          <Input value={form.company_name} onChange={setCompanyName} maxLength={isIndividual ? 255 : 50} placeholder={isIndividual ? "e.g. John Smith" : "e.g. Al Futtaim Group"} />
        </Field>
        <NameLookup
          name={form.company_name}
          excludeId={form._id}
          active={mode === "new"}
          canOverride={canApprove}
          override={override}
          onOverride={setOverride}
          onExactMatch={setExactMatch}
          onOpen={async (id) => onOpenExisting(await accountsApi.get(id))}
        />
        {!isIndividual && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="New Client Category" required={req("client_category")}>
                <Select value={form.client_category || ""} onChange={set("client_category")}>
                  <option value="">— select —</option>
                  <option value="Under Formation">Under Formation</option>
                  <option value="Existing">Existing</option>
                </Select>
              </Field>
              <Field label="Country of Incorporation / Registration" required={req("country")}>
                <CountrySelect value={form.country} onChange={set("country")} countries={countries} />
              </Field>
            </div>
            {form.client_category === "Under Formation" && (
              <p className="text-[11px] text-gray-500 -mt-2 mb-3">Licence, incorporation, address and tax details may be left blank until the company is formed.</p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Contact Mobile" required={req("contact_mobile_number")}>
                <MobileNumberInput code={form.contact_mobile_country_code} number={form.contact_mobile_number} options={dialOptions}
                  onCode={setValue("contact_mobile_country_code")} onNumber={setValue("contact_mobile_number")} placeholder="e.g. 43334444" />
              </Field>
              <Field label="Contact Email" required={req("contact_email")}><Input type="email" value={form.contact_email || ""} onChange={set("contact_email")} placeholder="e.g. info@company.com" /></Field>
            </div>
            <Field label="Nature of Services sought" required={req("nature_of_services_sought")}>
              <MultiSelect options={alphabetical(selectableCodes(servicesForEntities(services.items, [form.anchor_entity, ...(form.non_anchor_entities || [])]), form.nature_of_services_sought))}
                value={form.nature_of_services_sought} onChange={setServicesSought} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <YesNo label="Is this a one-time service?" value={form.is_one_time_service} onChange={setValue("is_one_time_service")} />
            </div>
          </>
        )}
        <Field label="Single Point of Contact (Client Contact Name)">
          <Input value={form.single_point_of_contact} onChange={set("single_point_of_contact")} placeholder="e.g. Jane Doe" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Anchor RM (SPOC)" required={req("spoc_id")}>
            <Select value={form.spoc_id || ""} onChange={(e) => setForm({ ...form, spoc_id: e.target.value, non_anchor_rm_ids: (form.non_anchor_rm_ids || []).filter((id) => id !== +e.target.value) })}>
              <option value="">— None —</option>
              {rms.map((u) => <option key={u.id} value={u.id}>{personLabel(u, rms)}</option>)}
            </Select>
          </Field>
          <Field label="Non-anchor RMs">
            <MultiSelect
              options={rms.filter((u) => u.id !== +form.spoc_id).map((u) => u.id)}
              getLabel={(id) => personLabel(users.find((u) => u.id === id), rms)}
              value={form.non_anchor_rm_ids}
              onChange={setValue("non_anchor_rm_ids")} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Anchor Triam Entity" required={req("anchor_entity")}>
            <Select value={form.anchor_entity || ""} onChange={(e) => setForm({ ...form, anchor_entity: e.target.value, non_anchor_entities: (form.non_anchor_entities || []).filter((x) => x !== e.target.value) })}>
              <option value="">— select —</option>
              {selectableCodes(entities.items, form.anchor_entity).map((t) => <option key={t} value={t}>{entities.labelOf(t)}</option>)}
            </Select>
          </Field>
          <Field label="Non-anchor Entities">
            <MultiSelect options={selectableCodes(entities.items, form.non_anchor_entities).filter((t) => t !== form.anchor_entity)} value={form.non_anchor_entities} onChange={setValue("non_anchor_entities")} />
          </Field>
        </div>
        {!isIndividual && (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Incorporation Certificate No." required={req("registration_number")}>
              <Input value={form.registration_number} onChange={set("registration_number")} placeholder="e.g. 123456" maxLength={30} />
            </Field>
            <Field label="License Number" required={req("license_number")}>
              <Input value={form.license_number} onChange={set("license_number")} placeholder="e.g. DIFC-LIC-9012" maxLength={30} />
            </Field>
            <Field label="Incorporation Date" required={req("incorporation_date")}>
              <DateInput max={today} value={form.incorporation_date || ""} onChange={set("incorporation_date")} />
            </Field>
          </div>
        )}

        <Field label="Tags">
          <MultiSelect options={selectableCodes(tags.items, form.tags)} value={form.tags} onChange={setValue("tags")} />
        </Field>
        </fieldset>

        <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100">
          {!locked && <button type="button" onClick={() => saveSection("core", true)} disabled={sectionStatus.core === "saving" || !sectionDirty("core")}
            title={sectionDirty("core") ? "" : "No changes to save"}
            className={`px-3 py-1.5 text-xs rounded-lg border disabled:cursor-not-allowed ${sectionDirty("core")
              ? "border-brand-600 bg-brand-600 text-white hover:bg-brand-700" : "border-gray-200 text-gray-400 bg-white"}`}>
            {sectionStatus.core === "saving" ? "Saving…" : "Save Client Info"}
          </button>}
          {sectionStatus.core === "saved" && <span className="text-xs text-emerald-600">Saved</span>}
          {sectionStatus.core === "error" && <span className="text-xs text-red-600">{sectionError.core || "Save failed"}</span>}
          {!form._id && <span className="text-xs text-gray-400">Save this first to unlock the sections below</span>}
        </div>

        {!isIndividual && (
          <>
            <Section title="Licensing & Regulatory" hasData={!!(form.licensing_authority || form.license_activities || form.license_start_date || form.license_expiry_date || form.is_regulated != null || form.license_category)}
              {...sectionProps("licensing")}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Registering Authority" required={req("licensing_authority")}>
                  {authorities.items.length ? (
                    <Select value={form.licensing_authority || ""} onChange={set("licensing_authority")}>
                      <option value="">— select —</option>
                      {selectableCodes(authorities.items, form.licensing_authority).map((a) => <option key={a} value={a}>{authorities.labelOf(a)}</option>)}
                    </Select>
                  ) : (
                    <Input value={form.licensing_authority} onChange={set("licensing_authority")} placeholder="e.g. DIFC, ADGM, DED" />
                  )}
                </Field>
                {form.licensing_authority === "Other" && (
                  <Field label="Registering Authority (Other)" required={req("licensing_authority_other")}>
                    <Input value={form.licensing_authority_other || ""} onChange={set("licensing_authority_other")} maxLength={100} />
                  </Field>
                )}
                <Field label="License Start Date" required={req("license_start_date")}><DateInput value={form.license_start_date || ""} onChange={set("license_start_date")} /></Field>
                <Field label="License Expiry Date" required={req("license_expiry_date")}><DateInput min={today} value={form.license_expiry_date || ""} onChange={set("license_expiry_date")} /></Field>
              </div>
              <Field label="Detailed Nature of Business carried out currently">
                <Textarea rows={2} value={form.nature_of_business} onChange={set("nature_of_business")} maxLength={1000} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="LEI, if registered"><Input value={form.lei_number} onChange={(e) => setForm({ ...form, lei_number: e.target.value.toUpperCase() })} maxLength={20} placeholder="20 letters / digits" /></Field>
                <Field label="LEI Expiry Date"><DateInput value={form.lei_expiry_date || ""} onChange={set("lei_expiry_date")} /></Field>
              </div>
              <div className="mb-3">
                <Field label="Licensed Activities" required={req("license_activities")}>
                  <Textarea rows={3} value={form.license_activities} onChange={set("license_activities")} maxLength={250} />
                  <p className="text-[11px] text-gray-400 text-right">{(form.license_activities || "").length}/250</p>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <YesNo label="Is entity regulated" required={req("is_regulated")} value={form.is_regulated} onChange={setValue("is_regulated")} />
              </div>
              {form.is_regulated && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Regulator" required={req("regulator_name")}>
                    <Select value={form.regulator_name || ""} onChange={set("regulator_name")}>
                      <option value="">— select —</option>
                      {selectableCodes(regulators.items, form.regulator_name).map((o) => <option key={o} value={o}>{regulators.labelOf(o)}</option>)}
                    </Select>
                  </Field>
                  {form.regulator_name === "Other" && (
                    <Field label="Other Regulator" required={req("regulator_other")}><Input value={form.regulator_other} onChange={set("regulator_other")} /></Field>
                  )}
                  <Field label="License Category" required={req("license_category")}><Input value={form.license_category} onChange={set("license_category")} maxLength={25} /></Field>
                  <Field label="Current regulatory license expiry" required={req("regulatory_license_expiry_date")}><DateInput value={form.regulatory_license_expiry_date || ""} onChange={set("regulatory_license_expiry_date")} /></Field>
                </div>
              )}
            </Section>

            <Section title="Registered Address" hasData={Object.values(form.registered_address || {}).some(Boolean)}
              {...sectionProps("registeredAddress")}>
              <AddressFields required={req("registered_address")} value={form.registered_address} onChange={setRegisteredAddress} countries={countries} />
            </Section>

            <Section title="Operating Address" hasData={Object.values(form.operating_address || {}).some(Boolean)}
              {...sectionProps("operatingAddress")}>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                <input type="checkbox" checked={sameAsRegistered} onChange={toggleSameAsRegistered} /> Same as Registered Address
              </label>
              <fieldset disabled={sameAsRegistered} className="min-w-0">
                <AddressFields required={req("operating_address")} value={form.operating_address} onChange={setOperatingAddress} countries={countries} />
              </fieldset>
            </Section>

            {/* Triam 12-11-2026: no VAT or Corporate Tax in the BVI, so offshore companies don't see those fields
                (unless a value was already saved); the Financial Year End stays, optional. */}
            <Section title={offshore ? "Financial Year" : "Tax"} hasData={!!(form.trn_vat_number || form.financial_year_end || form.corp_tax_registered)}
              {...sectionProps("tax")}>
              {offshore && (
                <p className="text-[11px] text-gray-500 mb-2">No VAT or Corporate Tax for offshore (BVI) companies. The Financial Year End is optional.</p>
              )}
              <div className="grid grid-cols-2 gap-3">
                {showVat && <Field label="TRN / VAT Registration No."><Input value={form.trn_vat_number} onChange={(e) => setForm({ ...form, trn_vat_number: e.target.value.replace(/\D/g, "") })} maxLength={15} inputMode="numeric" /></Field>}
                <Field label={`Financial Year End${form.financial_year_end ? ` (${fmtFYE(form.financial_year_end)})` : ""}`} required={req("financial_year_end")}>
                  <div className="flex gap-2">
                    <Select value={parseFYE(form.financial_year_end).day} onChange={(e) => setForm({ ...form, financial_year_end: toFYE(parseFYE(form.financial_year_end).month || "12", e.target.value) })}>
                      <option value="">Day</option>
                      {Array.from({ length: daysIn(parseFYE(form.financial_year_end).month) }, (_, i) => <option key={i + 1} value={String(i + 1)}>{String(i + 1).padStart(2, "0")}</option>)}
                    </Select>
                    <Select value={parseFYE(form.financial_year_end).month} onChange={(e) => setForm({ ...form, financial_year_end: toFYE(e.target.value, parseFYE(form.financial_year_end).day || "1") })}>
                      <option value="">Month</option>
                      {MONTHS.map((m, i) => <option key={m} value={String(i + 1)}>{m}</option>)}
                    </Select>
                  </div>
                </Field>
              </div>
              {showCorpTax && <div className="grid grid-cols-2 gap-3">
                <YesNo label="Corporate Tax Registered" required={req("corp_tax_registered")} value={form.corp_tax_registered} onChange={setValue("corp_tax_registered")} />
              </div>}
              {showCorpTax && form.corp_tax_registered && (
                <Field label="Corp Tax Registration No. / TAN"><Input value={form.corp_tax_registration_number} onChange={(e) => setForm({ ...form, corp_tax_registration_number: e.target.value.replace(/\D/g, "") })} maxLength={15} inputMode="numeric" /></Field>
              )}
            </Section>
          </>
        )}

        {isIndividual && (
          <Section title="Individual Details" hasData={!!(form.date_of_birth || form.country_of_birth || form.nationality || form.individual_mobile_number || form.individual_email || form.country_of_residence || form.is_pep || (form.nature_of_services_sought || []).length > 0)}
            {...sectionProps("individual")}>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date of Birth" required={req("date_of_birth")}><DateInput value={form.date_of_birth || ""} onChange={set("date_of_birth")} /></Field>
              <Field label="Country of Birth" required={req("country_of_birth")}><CountrySelect value={form.country_of_birth} onChange={set("country_of_birth")} countries={countries} /></Field>
              <Field label="Nationality" required={req("nationality")}><CountrySelect value={form.nationality} onChange={set("nationality")} countries={countries} /></Field>
              <Field label="Passport Expiry Date" required={req("passport_expiry_date")}><DateInput value={form.passport_expiry_date || ""} onChange={set("passport_expiry_date")} /><PassportNote value={form.passport_expiry_date} /></Field>
              <Field label="Contact Email" required={req("individual_email")}><Input type="email" value={form.individual_email} onChange={set("individual_email")} /></Field>
              <Field label="Country of Residence" required={req("country_of_residence")}><CountrySelect value={form.country_of_residence} onChange={(e) => setForm({ ...form, country_of_residence: e.target.value, ...isdFor(e.target.value, "individual_mobile_country_code") })} countries={countries} /></Field>
            </div>
            <Field label="Contact Mobile" required={req("individual_mobile_number")}>
              <MobileNumberInput code={form.individual_mobile_country_code} number={form.individual_mobile_number} options={dialOptions}
                onCode={setValue("individual_mobile_country_code")} onNumber={setValue("individual_mobile_number")} />
            </Field>
            <Field label="Nature of Services Sought" required={req("nature_of_services_sought")}>
              <MultiSelect options={alphabetical(selectableCodes(services.items, form.nature_of_services_sought))} value={form.nature_of_services_sought} onChange={setServicesSought} />
            </Field>
            <Field label="Detailed Nature of Profession / Business">
              <Textarea rows={2} value={form.nature_of_business} onChange={set("nature_of_business")} maxLength={1000} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <YesNo label="Is this a one-time service?" value={form.is_one_time_service} onChange={setValue("is_one_time_service")} />
            </div>

            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1.5">Residential Address</p>
            <AddressFields required={req("residential_address")} value={form.residential_address} onChange={setValue("residential_address")} countries={countries} />

            {isUAE(form.country_of_residence) && (
              <div className="grid grid-cols-2 gap-3 mt-3">
                <Field label="UAE Visa No."><Input value={form.uae_visa_number} onChange={set("uae_visa_number")} /></Field>
                <Field label="UAE Visa Expiry"><DateInput value={form.uae_visa_expiry || ""} onChange={set("uae_visa_expiry")} /></Field>
              </div>
            )}

            <label className="flex items-center gap-2 text-xs text-gray-700 mt-3">
              <input type="checkbox" checked={!!form.is_pep} onChange={setChecked("is_pep")} /> Politically Exposed Person (PEP)
            </label>
          </Section>
        )}

        <Section title="Introducer" hasData={form.has_introducer != null} {...sectionProps("introducer")}>
          <div className="grid grid-cols-2 gap-3">
            <YesNo label="Introduced by a third party" required={req("has_introducer")} value={form.has_introducer} onChange={setValue("has_introducer")} />
          </div>
          {form.has_introducer && (
            <Field label="Introducer Name" required={req("introducer_name")}><Input value={form.introducer_name} onChange={set("introducer_name")} /></Field>
          )}
        </Section>

        {form._id && (
          // BRD §12 step 8 / §16 — documents are filed against the Client ID. Saved on upload. Triam UAT
          // 26-10-2026: each section has its own — the firm's here, each person's in their record below.
          <Section title={isIndividual ? "Client Documents" : "Firm Documents"} hasData={WITH_RM_STATUSES.includes(form.profile_status)}>
            <ClientDocumentsFolder accountId={form._id} scope="client" individual={isIndividual}
              onboarding={WITH_RM_STATUSES.includes(form.profile_status)} onChange={() => setRefreshKey((k) => k + 1)} />
          </Section>
        )}

        {/* BRD §5.1–5.3 — the people behind the client, one section each, as many records as needed.
            Each person is saved on its own. */}
        {(isIndividual ? [["Joint Holder", "Joint Holders"]]
          : isFoundation(form) ? [["Founder", "Founders"], ["Council Member", "Council Members"], ["Beneficiary", "Beneficiaries"], ["Guardian", "Guardians"], ["Authorised Signatory", "Authorised Signatories"]]
          : [["Shareholder", "Shareholder / UBO Information"], ["Director", "Directors"], ["Authorised Signatory", "Authorised Signatories"]]
        ).map(([role, title]) => (
          <Section key={role} title={title} hasData={!!form._id}>
            {form._id ? (
              <Embedded>
                <AccountPartyModal role={role} account={{ id: form._id, account_type: form.account_type, company_name: form.company_name }}
                  onClose={() => {}} onChange={() => { setRefreshKey((k) => k + 1); onChanged(); }} />
              </Embedded>
            ) : (
              <p className="text-xs text-gray-500">Save Client Info first.</p>
            )}
          </Section>
        ))}

        {/* Triam UAT 26-10-2026: mandatory for every new client, completed by the RM / Sales Manager. */}
        {/* Triam UAT 05-11-2026: for Individual and Entity clients; the report is filed under Documents. */}
        <Section title="Name Screening" hasData={!!form.screening_date} {...sectionProps("screening")}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Screening Date"><DateInput max={today} value={form.screening_date || ""} onChange={set("screening_date")} /></Field>
          </div>
          <p className="text-[11px] text-gray-500">File the screening report in the client's documents, or in the person's own record.</p>
        </Section>

        <Section title="Biz Rationale Report" hasData={!!(form.br_person_met || form.br_rationale)} {...sectionProps("bizRationale")}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Full Name of the Person Met" required={req("br_person_met")}><Input value={form.br_person_met} onChange={set("br_person_met")} maxLength={255} /></Field>
            <Field label="Place of Meeting with the Customer" required={req("br_meeting_place")}><Input value={form.br_meeting_place} onChange={set("br_meeting_place")} maxLength={255} /></Field>
            <Field label="Date of Meeting with the Customer" required={req("br_meeting_date")}><DateInput value={form.br_meeting_date || ""} onChange={set("br_meeting_date")} max={today} /></Field>
            <Field label="Time of Meeting with the Customer" required={req("br_meeting_time")}><Input type="time" value={form.br_meeting_time} onChange={set("br_meeting_time")} /></Field>
          </div>
          <Field label="Mode of Meeting" required={req("br_meeting_mode")}>
            <div className="flex gap-5 text-sm text-gray-700 py-1">
              {["Face to Face", "Video Call"].map((m) => (
                <label key={m} className="flex items-center gap-1.5">
                  <input type="radio" name="br_meeting_mode" checked={form.br_meeting_mode === m} onChange={() => setForm({ ...form, br_meeting_mode: m })} /> {m}
                </label>
              ))}
            </div>
          </Field>
          <Field label="Business Rationale for the Relationship" required={req("br_rationale")}>
            <p className="text-[11px] text-gray-500 mb-1">The purpose of establishing the relationship, the services to be obtained at the start of the relationship and the likely introduction of new services in the next 2 years.</p>
            <Textarea rows={5} value={form.br_rationale} onChange={set("br_rationale")} maxLength={4000} />
          </Field>
        </Section>

        <Section title="Services Obtained *" hasData={(form.services_obtained || []).length > 0} {...sectionProps("services")}>
          <p className="text-[11px] text-gray-500 mb-2">Filled in from Nature of Services sought. Change it if Triam provides different services.</p>
          <MultiSelect options={alphabetical(obtainableServices)} value={form.services_obtained} onChange={setValue("services_obtained")} />
        </Section>

        <Section title="Engagement" hasData={form.engagement_letter_signed != null || !!form.engagement_letter_valid_until}
          {...sectionProps("profileStatus")}>
          <div className="grid grid-cols-2 gap-3">
            <YesNo label="Engagement Letter Signed" required={req("engagement_letter_signed")} value={form.engagement_letter_signed} onChange={setValue("engagement_letter_signed")} />
            {form.engagement_letter_signed && (
              <Field label="Engagement Letter Valid Until" required={req("engagement_letter_valid_until")}><DateInput value={form.engagement_letter_valid_until || ""} onChange={set("engagement_letter_valid_until")} /></Field>
            )}
          </div>
        </Section>

        {/* Triam UAT 26-10-2026: this section belongs to Compliance, not Client Onboarding — shown to
            Compliance and the Approver (reviewing from Compliance Approval), editable by Compliance only. */}
        {showCdd && (
        <Section title="Customer Risk Assessment / KYC & AML (Compliance)" hasData={!!(form.risk_rating || form.cdd_completion_date)}
          {...sectionProps("aml")} readOnly={false} onSave={cddEditable ? () => saveSection("aml") : undefined}>
          {!cddEditable && (
            <p className="text-xs text-gray-500 mb-2">
              {canCdd ? "Editable while the client is with Compliance." : "Completed by Compliance (MLRO) after the client is submitted."}
            </p>
          )}
          {riskLinks.length > 0 && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2">
              <div className="text-xs font-semibold text-red-700 mb-1">High-risk countries</div>
              <ul className="text-xs text-red-800 space-y-0.5">
                {riskLinks.map((l, i) => <li key={i}><span className="font-semibold">{l.country}</span> · {l.who} · {l.field}</li>)}
              </ul>
            </div>
          )}
          <fieldset disabled={!cddEditable} className="grid grid-cols-2 gap-3 disabled:opacity-70">
            <Field label="CDD/AML Risk Level">
              <Select value={form.risk_rating || ""} onChange={set("risk_rating")}>
                <option value="">— Not set —</option>
                {RISK_OPTIONS.map((r) => <option key={r}>{r}</option>)}
              </Select>
            </Field>
            <Field label="CDD Completion Date"><DateInput value={form.cdd_completion_date || ""} onChange={set("cdd_completion_date")} /></Field>
            <Field label="KYC Verification performed by">
              <Select value={form.kyc_verified_by || ""} onChange={set("kyc_verified_by")}>
                <option value="">— select RM —</option>
                {[...new Set([...(form.kyc_verified_by ? [form.kyc_verified_by] : []), ...rms.map((u) => u.name)])].map((n) => <option key={n} value={n}>{n}</option>)}
              </Select>
            </Field>
            {form.risk_rating === "High" && (
              <Field label="Reason for EDD (up to 250 characters)" required><Textarea rows={3} value={form.edd_reason} onChange={set("edd_reason")} maxLength={250} /></Field>
            )}
          </fieldset>
          {form.next_aml_review_date && (
            <p className="text-xs text-gray-400">Next AML Review Date: <span className="font-medium text-gray-600">{fmtDate(form.next_aml_review_date)}</span></p>
          )}
        </Section>
        )}
      </div>
      {/* Always in view while scrolling the long form. */}
      <div className="sticky bottom-0 z-10 flex justify-end gap-3 mt-5 -mx-1 px-1 py-3 bg-white/95 backdrop-blur border-t border-gray-100">
        <button onClick={cancel} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">{readOnlyUser ? "Close" : "Cancel"}</button>
        {!readOnlyUser && <button onClick={save} disabled={saving || locked || (mode === "edit" && !anyDirty)}
          title={myDraft ? "Saves into your draft amendment" : "Saves the client as a draft; nothing goes to Compliance yet"}
          className="px-4 py-2 text-sm border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 disabled:opacity-50">
          {saving ? "Saving..." : "Save"}
        </button>}
        {canSubmit && (
          <button onClick={submit} disabled={saving}
            title="Saves, then sends to Compliance for approval"
            className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
            style={{ background: "#1a3a5c" }}>
            {myDraft ? "Submit to Compliance" : "Submit for Approval"}
          </button>
        )}
      </div>
    </Modal>
  );
}
