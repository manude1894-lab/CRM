import React, { useEffect, useState } from "react";
import { accountsApi, workflowApi } from "../../api/endpoints";
import { Icon, Modal, Field, Input, Select, MultiSelect, CountrySelect, Textarea, DateInput } from "../ui";
import NameLookup from "./NameLookup";
import CompletenessChecklist from "./CompletenessChecklist";
import WorkflowBar from "./WorkflowBar";
import AmendmentBar from "./AmendmentBar";
import ClientDocumentsFolder from "./ClientDocumentsFolder";
import { useAuthStore } from "../../store/auth";
import { MONTHS, parseFYE, toFYE, fmtFYE, daysIn } from "../../utils/fye";
import { toast } from "../../store/toast";
import {
  fmtDate, REGULATOR_OPTIONS, TAG_OPTIONS, SERVICES_OBTAINED_OPTIONS,
  PROFILE_STATUS_OPTIONS, COUNTRY_CALLING_CODES, TRIAM_ENTITY_OPTIONS, isUAE,
} from "../../utils/constants";
import {
  PRIORITY_OPTIONS, RISK_OPTIONS, KYC_STATUS_OPTIONS, BLANK_ADDRESS, SECTION_FIELDS,
  buildAccountPayload, buildSectionPatch, validateCoreFields, accountToForm,
} from "./accountForm";
import { useMasters } from "../../hooks/useMasters";
import { selectableCodes, servicesForEntities } from "../../hooks/masterUtils";

const Section = ({ title, children, hasData, onSave, status, error, dirty = true }) => {
  const [open, setOpen] = useState(!!hasData);
  return (
    <div className="mb-2 border border-gray-100 rounded-lg overflow-hidden">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide flex items-center gap-1.5">
          {title}
          {hasData && <span className="w-1.5 h-1.5 rounded-full bg-brand-500 flex-shrink-0" />}
        </span>
        <Icon name="chevronRight" size={14} className={`text-gray-400 transition-transform flex-shrink-0 ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="px-3 py-3">
          {children}
          {onSave && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
              <button type="button" onClick={onSave} disabled={status === "saving" || !dirty} title={dirty ? "" : "No changes to save"}
                className={`px-3 py-1.5 text-xs rounded-lg border disabled:cursor-not-allowed ${dirty
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
const YesNo = ({ label, value, onChange }) => (
  <Field label={`${label} *`}>
    <Select value={value === true ? "yes" : value === false ? "no" : ""} onChange={(e) => onChange(e.target.value === "yes" ? true : e.target.value === "no" ? false : null)}>
      <option value="">— select —</option>
      <option value="yes">Yes</option>
      <option value="no">No</option>
    </Select>
  </Field>
);

const AddressFields = ({ value, onChange }) => {
  const v = value || BLANK_ADDRESS;
  const set = (k) => (e) => onChange({ ...v, [k]: e.target.value });
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Address Line 1"><Input value={v.line1 || ""} onChange={set("line1")} /></Field>
      <Field label="Address Line 2"><Input value={v.line2 || ""} onChange={set("line2")} /></Field>
      <Field label="Landmark"><Input value={v.landmark || ""} onChange={set("landmark")} /></Field>
      <Field label="City"><Input value={v.city || ""} onChange={set("city")} /></Field>
      <Field label="ZIP Code"><Input value={v.zip || ""} onChange={set("zip")} /></Field>
      <Field label="P.O. Box No."><Input value={v.po_box || ""} onChange={set("po_box")} /></Field>
      <Field label="Country"><Input value={v.country || ""} onChange={set("country")} /></Field>
    </div>
  );
};

/**
 * New / Edit Client modal. Owns its form state; the parent remounts it (via `key`) to open a different client.
 * - onChanged: called after any successful save so the parent can reload the list.
 * - onOpenExisting(account): user picked an existing client from the duplicate warning.
 */
export default function AccountFormModal({ initialForm, users, countries, onClose, onChanged, onOpenExisting, hideWorkflow = false, hideDocuments = false }) {
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
  // The search name follows the legal name until the user edits it themselves.
  const [searchTouched, setSearchTouched] = useState(!!initialForm.search_name);
  const [refreshKey, setRefreshKey] = useState(0);
  // BRD §13 — an approved client is changed only through an amendment that Compliance approves.
  const [amendment, setAmendment] = useState(null);
  const [previewOf, setPreviewOf] = useState(null); // request id whose staged values are loaded in the form
  const approvedClient = ["Approved", "Active", "Inactive", "Marked for Exit"].includes(form.profile_status);
  const myDraft = amendment?.request?.status === "Draft" && amendment.actions.includes("submit");
  const amendLocked = !!form._id && approvedClient && !myDraft;
  const locked = ["Awaiting Approval", "Exited"].includes(form.profile_status) || amendLocked;
  // Triam mark-up §7/§11: only Compliance completes the CDD section — before submission, while the
  // client is with Compliance, or in an amendment of an approved client.
  const canCdd = useAuthStore((st) => st.can("client.cdd_edit"));
  const [stage, setStage] = useState(null);
  useEffect(() => {
    if (form._id && form.profile_status === "Awaiting Approval") workflowApi.get(form._id).then((w) => setStage(w.stage)).catch(() => setStage(null));
    else setStage(null);
  }, [form._id, form.profile_status, refreshKey]);
  const cddEditable = canCdd && (!locked || (form.profile_status === "Awaiting Approval" && stage === "Compliance"));
  const onAmendmentState = (s) => {
    setAmendment(s);
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
    setForm((f) => ({ ...f, profile_status: state.status, _status_updated_at: state.status_updated_at }));
    setRefreshKey((k) => k + 1);
    onChanged();
  };
  const canApprove = useAuthStore((s) => s.can("client.approve"));

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const setChecked = (key) => (e) => setForm({ ...form, [key]: e.target.checked });
  const setValue = (key) => (v) => setForm({ ...form, [key]: v });
  const rms = users.filter((u) => u.role === "rm");
  const isIndividual = form.account_type === "Individual";
  // BRD §18 — admin-managed lists; the old constants are the fallback until the API answers.
  const entities = useMasters("triam_entity", TRIAM_ENTITY_OPTIONS);
  const services = useMasters("service", SERVICES_OBTAINED_OPTIONS);
  const tags = useMasters("tag", TAG_OPTIONS);
  const regulators = useMasters("regulator", REGULATOR_OPTIONS);
  const authorities = useMasters("licensing_authority", []);

  const setCompanyName = (e) => {
    const value = e.target.value;
    setForm((f) => ({ ...f, company_name: value, ...(searchTouched ? {} : { search_name: value.replace(/\s+/g, " ").trim().slice(0, 120) }) }));
  };
  const setSearchName = (e) => { setSearchTouched(true); setForm((f) => ({ ...f, search_name: e.target.value })); };

  // Create payload extras + the duplicate gate (BRD §3).
  const duplicateBlock = () => {
    if (!exactMatch) return null;
    if (!canApprove) return "A client with this exact name already exists — open it instead, or ask an approver to create a duplicate.";
    if (!override.allow) return "A client with this exact name already exists — tick 'Create anyway' and give a reason to continue.";
    if ((override.reason || "").trim().length < 10) return "Give a meaningful reason (at least 10 characters) for creating a duplicate client.";
    return null;
  };
  const withOverride = (payload) => (exactMatch && override.allow ? { ...payload, allow_duplicate: true, duplicate_reason: override.reason.trim() } : payload);

  const save = async () => {
    // Industry is only enforced when creating a client, so older records without one can still be edited.
    const invalid = mode === "new" ? (validateCoreFields(form) || duplicateBlock()) : (!form.company_name?.trim() && "Company name is required");
    if (invalid) return toast.error(invalid);
    try {
      setSaving(true);
      const payload = buildAccountPayload(form);
      if (mode === "edit") await accountsApi.update(form._id, payload);
      else await accountsApi.create(withOverride(payload));
      onChanged();
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || (mode === "edit" ? "Failed to update client" : "Failed to create client"));
    } finally { setSaving(false); }
  };

  // Client CRM-change-request item 19 — per-section Save, so each section validates and
  // persists independently instead of only surfacing errors at the very bottom of the form.
  const saveSection = async (key, isCore = false) => {
    setSectionStatus((s) => ({ ...s, [key]: "saving" }));
    setSectionError((s) => ({ ...s, [key]: null }));
    const snapshot = form;
    try {
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
        setSearchTouched(true);
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

  const sectionProps = (key) => ({ onSave: locked ? undefined : () => saveSection(key), status: sectionStatus[key], error: sectionError[key], dirty: sectionDirty(key) });
  const today = new Date().toISOString().slice(0, 10);

  return (
    <Modal title={mode === "edit" ? "Edit Client" : "New Client"} onClose={onClose}>
      <div className="space-y-3">
        {form._id && (
          // BRD §11 "status visible on every client profile screen" + §19 Client ID
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100 text-xs text-gray-600">
            <span>Client ID <span className="font-mono font-semibold text-gray-800">{form._client_id || "—"}</span></span>
            {form._status_updated_at && <span>Status last updated {fmtDate(form._status_updated_at)}</span>}
          </div>
        )}
        {form._id && !hideWorkflow && <WorkflowBar accountId={form._id} refreshKey={refreshKey} onChanged={onWorkflowChanged} />}
        {form._id && approvedClient && (
          <AmendmentBar accountId={form._id} refreshKey={refreshKey} onState={onAmendmentState} onDecided={onAmendmentDecided} />
        )}
        {!locked && !approvedClient && <CompletenessChecklist accountId={form._id} refreshKey={refreshKey} />}
        {mode === "new" && form._prospect_uid && (
          <div className="mb-3 text-xs rounded-lg bg-brand-50 text-brand-700 px-3 py-2">
            Creating the client from prospect <span className="font-mono font-semibold">{form._prospect_uid}</span>. This is the client's
            temporary ID until Compliance approves it and the Client ID is issued.
          </div>
        )}
        <Field label="Client Type">
          <Select value={form.account_type} onChange={set("account_type")}>
            <option>Corporate</option>
            <option>Individual</option>
          </Select>
        </Field>
        <Field label={isIndividual ? "Full Name (as per passport) *" : "Company Name *"}>
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
        <Field label="Unique Search Name *">
          <Input value={form.search_name || ""} onChange={setSearchName} maxLength={120} placeholder="Short name used to find this client" />
        </Field>
        {!isIndividual && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="New Client Category *">
                <Select value={form.client_category || ""} onChange={set("client_category")}>
                  <option value="">— select —</option>
                  <option value="Under Formation">Under Formation</option>
                  <option value="Existing">Existing</option>
                </Select>
              </Field>
              <Field label="Country of Incorporation / Registration">
                <CountrySelect value={form.country} onChange={set("country")} countries={countries} />
              </Field>
            </div>
            {form.client_category === "Under Formation" && (
              <p className="text-[11px] text-gray-500 -mt-2 mb-3">Licence and incorporation details may be left blank until the company is formed.</p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label="Contact Mobile *">
                <div className="flex gap-2">
                  <Select value={form.contact_mobile_country_code || ""} onChange={set("contact_mobile_country_code")} className="w-40 flex-shrink-0">
                    <option value="">Code</option>
                    {COUNTRY_CALLING_CODES.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                  </Select>
                  <Input value={form.contact_mobile_number || ""} onChange={set("contact_mobile_number")} maxLength={12} placeholder="e.g. 43334444" />
                </div>
              </Field>
              <Field label="Contact Email *"><Input type="email" value={form.contact_email || ""} onChange={set("contact_email")} placeholder="e.g. info@company.com" /></Field>
            </div>
            <Field label="Nature of Services sought *">
              <MultiSelect options={selectableCodes(servicesForEntities(services.items, [form.anchor_entity, ...(form.non_anchor_entities || [])]), form.nature_of_services_sought)}
                value={form.nature_of_services_sought} onChange={setValue("nature_of_services_sought")} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <YesNo label="Is this a one-time service?" value={form.is_one_time_service} onChange={setValue("is_one_time_service")} />
            </div>
            <Field label="Website">
              <Input value={form.website} onChange={set("website")} placeholder="e.g. https://company.com" />
            </Field>
          </>
        )}
        <Field label="Key Contacts">
          <Input value={form.key_contacts} onChange={set("key_contacts")} placeholder="e.g. John Smith - CEO" />
        </Field>
        <Field label="Single Point of Contact (Client Contact Name)">
          <Input value={form.single_point_of_contact} onChange={set("single_point_of_contact")} placeholder="e.g. Jane Doe" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Existing Relationship">
            <Select value={form.existing_relationship} onChange={set("existing_relationship")}>
              <option>No</option>
              <option>Yes</option>
            </Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Anchor RM (SPOC)">
            <Select value={form.spoc_id || ""} onChange={(e) => setForm({ ...form, spoc_id: e.target.value, non_anchor_rm_ids: (form.non_anchor_rm_ids || []).filter((id) => id !== +e.target.value) })}>
              <option value="">— None —</option>
              {rms.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </Select>
          </Field>
          <Field label="Non-anchor RMs">
            <MultiSelect
              options={rms.filter((u) => u.id !== +form.spoc_id).map((u) => u.id)}
              getLabel={(id) => users.find((u) => u.id === id)?.name}
              value={form.non_anchor_rm_ids}
              onChange={setValue("non_anchor_rm_ids")} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Anchor Triam Entity *">
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
            <Field label="Incorporation Certificate No.">
              <Input value={form.registration_number} onChange={set("registration_number")} placeholder="e.g. 123456" maxLength={30} />
            </Field>
            <Field label="License Number">
              <Input value={form.license_number} onChange={set("license_number")} placeholder="e.g. DIFC-LIC-9012" maxLength={30} />
            </Field>
            <Field label="Incorporation Date">
              <DateInput max={today} value={form.incorporation_date || ""} onChange={set("incorporation_date")} />
            </Field>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="KYC Status">
            <Select value={form.kyc_status} onChange={set("kyc_status")}>
              {KYC_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
            </Select>
          </Field>
        </div>

        <Field label="Tags">
          <MultiSelect options={selectableCodes(tags.items, form.tags)} value={form.tags} onChange={setValue("tags")} />
        </Field>

        <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-100">
          <button type="button" onClick={() => saveSection("core", true)} disabled={locked || sectionStatus.core === "saving" || !sectionDirty("core")}
            title={sectionDirty("core") ? "" : "No changes to save"}
            className={`px-3 py-1.5 text-xs rounded-lg border disabled:cursor-not-allowed ${!locked && sectionDirty("core")
              ? "border-brand-600 bg-brand-600 text-white hover:bg-brand-700" : "border-gray-200 text-gray-400 bg-white"}`}>
            {sectionStatus.core === "saving" ? "Saving…" : "Save Client Info"}
          </button>
          {sectionStatus.core === "saved" && <span className="text-xs text-emerald-600">Saved</span>}
          {sectionStatus.core === "error" && <span className="text-xs text-red-600">{sectionError.core || "Save failed"}</span>}
          {!form._id && <span className="text-xs text-gray-400">Save this first to unlock the sections below</span>}
        </div>

        {!isIndividual && (
          <>
            <Section title="Licensing & Regulatory" hasData={!!(form.licensing_authority || form.license_activities || form.license_start_date || form.license_expiry_date || form.is_regulated != null || form.license_category)}
              {...sectionProps("licensing")}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Licensing Authority">
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
                  <Field label="Licensing Authority (Other) *">
                    <Input value={form.licensing_authority_other || ""} onChange={set("licensing_authority_other")} maxLength={100} />
                  </Field>
                )}
                <Field label="License Start Date"><DateInput value={form.license_start_date || ""} onChange={set("license_start_date")} /></Field>
                <Field label="License Expiry Date"><DateInput min={today} value={form.license_expiry_date || ""} onChange={set("license_expiry_date")} /></Field>
              </div>
              <Field label="Detailed Nature of Business carried out currently">
                <Textarea rows={2} value={form.nature_of_business} onChange={set("nature_of_business")} maxLength={1000} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="LEI, if registered"><Input value={form.lei_number} onChange={(e) => setForm({ ...form, lei_number: e.target.value.toUpperCase() })} maxLength={20} placeholder="20 letters / digits" /></Field>
                <Field label="LEI Expiry Date"><DateInput value={form.lei_expiry_date || ""} onChange={set("lei_expiry_date")} /></Field>
              </div>
              <div className="mb-3">
                <Field label={form.client_category === "Under Formation" ? "Licensed Activities" : "Licensed Activities *"}>
                  <Textarea rows={3} value={form.license_activities} onChange={set("license_activities")} maxLength={250} />
                  <p className="text-[11px] text-gray-400 text-right">{(form.license_activities || "").length}/250</p>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <YesNo label="Is entity regulated" value={form.is_regulated} onChange={setValue("is_regulated")} />
              </div>
              {form.is_regulated && (
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Regulator">
                    <Select value={form.regulator_name || ""} onChange={set("regulator_name")}>
                      <option value="">— select —</option>
                      {selectableCodes(regulators.items, form.regulator_name).map((o) => <option key={o} value={o}>{regulators.labelOf(o)}</option>)}
                    </Select>
                  </Field>
                  {form.regulator_name === "Other" && (
                    <Field label="Other Regulator"><Input value={form.regulator_other} onChange={set("regulator_other")} /></Field>
                  )}
                  <Field label="License Category"><Input value={form.license_category} onChange={set("license_category")} maxLength={25} /></Field>
                  <Field label="Current regulatory license expiry *"><DateInput value={form.regulatory_license_expiry_date || ""} onChange={set("regulatory_license_expiry_date")} /></Field>
                </div>
              )}
            </Section>

            <Section title="Registered Address" hasData={Object.values(form.registered_address || {}).some(Boolean)}
              {...sectionProps("registeredAddress")}>
              <AddressFields value={form.registered_address} onChange={setValue("registered_address")} />
            </Section>

            <Section title="Operating Address" hasData={Object.values(form.operating_address || {}).some(Boolean)}
              {...sectionProps("operatingAddress")}>
              <AddressFields value={form.operating_address} onChange={setValue("operating_address")} />
            </Section>

            <Section title="Tax" hasData={!!(form.trn_vat_number || form.financial_year_end || form.corp_tax_registered)}
              {...sectionProps("tax")}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="TRN / VAT Registration No."><Input value={form.trn_vat_number} onChange={(e) => setForm({ ...form, trn_vat_number: e.target.value.replace(/\D/g, "") })} maxLength={15} inputMode="numeric" /></Field>
                <Field label={`Financial Year End${form.financial_year_end ? ` — ${fmtFYE(form.financial_year_end)}` : ""}`}>
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
              <div className="grid grid-cols-2 gap-3">
                <YesNo label="Corporate Tax Registered" value={form.corp_tax_registered} onChange={setValue("corp_tax_registered")} />
              </div>
              {form.corp_tax_registered && (
                <Field label="Corp Tax Registration No. / TAN"><Input value={form.corp_tax_registration_number} onChange={(e) => setForm({ ...form, corp_tax_registration_number: e.target.value.replace(/\D/g, "") })} maxLength={15} inputMode="numeric" /></Field>
              )}
            </Section>
          </>
        )}

        {isIndividual && (
          <Section title="Individual Details" hasData={!!(form.date_of_birth || form.country_of_birth || form.nationality || form.passport_number || form.occupation || form.individual_mobile_number || form.individual_email || form.country_of_residence || form.source_of_funds || form.source_of_wealth || form.is_pep || (form.nature_of_services_sought || []).length > 0)}
            {...sectionProps("individual")}>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date of Birth"><DateInput value={form.date_of_birth || ""} onChange={set("date_of_birth")} /></Field>
              <Field label="Country of Birth"><CountrySelect value={form.country_of_birth} onChange={set("country_of_birth")} countries={countries} /></Field>
              <Field label="Nationality"><CountrySelect value={form.nationality} onChange={set("nationality")} countries={countries} /></Field>
              <Field label="Passport Number"><Input value={form.passport_number} onChange={set("passport_number")} /></Field>
              <Field label="Passport Expiry"><DateInput value={form.passport_expiry_date || ""} onChange={set("passport_expiry_date")} /></Field>
              <Field label="Occupation"><Input value={form.occupation} onChange={set("occupation")} /></Field>
              <Field label="Email"><Input type="email" value={form.individual_email} onChange={set("individual_email")} /></Field>
              <Field label="Country of Residence"><CountrySelect value={form.country_of_residence} onChange={set("country_of_residence")} countries={countries} /></Field>
            </div>
            <Field label="Mobile">
              <div className="flex gap-2">
                <Select value={form.individual_mobile_country_code || ""} onChange={set("individual_mobile_country_code")} className="w-40 flex-shrink-0">
                  <option value="">Code</option>
                  {COUNTRY_CALLING_CODES.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
                </Select>
                <Input value={form.individual_mobile_number || ""} onChange={set("individual_mobile_number")} maxLength={12} placeholder="e.g. 501234567" />
              </div>
            </Field>
            <Field label="Source of Funds"><Input value={form.source_of_funds} onChange={set("source_of_funds")} placeholder="e.g. Salary, business income" /></Field>
            <Field label="Source of Wealth"><Input value={form.source_of_wealth} onChange={set("source_of_wealth")} placeholder="e.g. Accumulated savings, inheritance" /></Field>
            <Field label="Nature of Services Sought *">
              <MultiSelect options={selectableCodes(services.items, form.nature_of_services_sought)} value={form.nature_of_services_sought} onChange={setValue("nature_of_services_sought")} />
            </Field>
            <Field label="Detailed Nature of Profession / Business">
              <Textarea rows={2} value={form.nature_of_business} onChange={set("nature_of_business")} maxLength={1000} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <YesNo label="Is this a one-time service?" value={form.is_one_time_service} onChange={setValue("is_one_time_service")} />
            </div>

            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1.5">Residential Address</p>
            <AddressFields value={form.residential_address} onChange={setValue("residential_address")} />

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
            <YesNo label="Introduced by a third party" value={form.has_introducer} onChange={setValue("has_introducer")} />
          </div>
          {form.has_introducer && (
            <Field label="Introducer Name"><Input value={form.introducer_name} onChange={set("introducer_name")} /></Field>
          )}
        </Section>

        {form._id && !hideDocuments && (
          // BRD §12 step 8 / §16 — documents are filed against the Client ID. Saved on upload.
          <Section title="Documents" hasData={["New", "WIP"].includes(form.profile_status)}>
            <ClientDocumentsFolder accountId={form._id} onboarding={["New", "WIP"].includes(form.profile_status)}
              onChange={() => setRefreshKey((k) => k + 1)} />
          </Section>
        )}

        <Section title="Services Obtained" hasData={(form.services_obtained || []).length > 0} {...sectionProps("services")}>
          <MultiSelect options={selectableCodes(servicesForEntities(services.items, [form.anchor_entity, ...(form.non_anchor_entities || [])]), form.services_obtained)} value={form.services_obtained} onChange={setValue("services_obtained")} />
        </Section>

        <Section title="Engagement" hasData={!!form.engagement_letter_signed || !!form.engagement_letter_valid_until}
          {...sectionProps("profileStatus")}>
          <p className="text-[11px] text-gray-400 mb-2">Profile status ({form.profile_status}) changes only through Submit / Approve and the status buttons at the top.</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Engagement Letter Valid Until"><DateInput value={form.engagement_letter_valid_until || ""} onChange={set("engagement_letter_valid_until")} /></Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-700">
            <input type="checkbox" checked={!!form.engagement_letter_signed} onChange={setChecked("engagement_letter_signed")} /> Engagement Letter Signed
          </label>
        </Section>

        <Section title="Customer Risk Assessment / KYC & AML (Compliance)" hasData={!!(form.risk_rating || form.cdd_completion_date)}
          {...sectionProps("aml")} onSave={cddEditable ? () => saveSection("aml") : undefined}>
          {!cddEditable && (
            <p className="text-xs text-gray-500 mb-2">
              {canCdd ? "Editable while the client is with Compliance." : "Completed by Compliance (MLRO) after the client is submitted."}
            </p>
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
              <Field label="Reason for EDD" required><Input value={form.edd_reason} onChange={set("edd_reason")} maxLength={25} /></Field>
            )}
          </fieldset>
          {form.next_aml_review_date && (
            <p className="text-xs text-gray-400">Next AML Review Date: <span className="font-medium text-gray-600">{fmtDate(form.next_aml_review_date)}</span> (auto-calculated from Risk Rating + CDD Completion Date)</p>
          )}
        </Section>
      </div>
      <div className="flex justify-end gap-3 mt-5">
        <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={save} disabled={saving || locked || (mode === "edit" && !anyDirty)}
          className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
          style={{ background: "#1a3a5c" }}>
          {saving ? "Saving..." : mode === "edit" ? (myDraft ? "Save to Amendment" : "Save Changes") : "Create Client"}
        </button>
      </div>
    </Modal>
  );
}
