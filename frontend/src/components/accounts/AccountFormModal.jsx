import React, { useState } from "react";
import { accountsApi } from "../../api/endpoints";
import { Icon, Modal, Field, Input, Select, MultiSelect, CountrySelect, Textarea } from "../ui";
import DuplicateWarning from "../DuplicateWarning";
import { toast } from "../../store/toast";
import {
  fmtDate, REGULATOR_OPTIONS, TAG_OPTIONS, SERVICES_OBTAINED_OPTIONS,
  PROFILE_STATUS_OPTIONS, AML_CLASSIFICATION_OPTIONS, COUNTRY_CALLING_CODES, TRIAM_ENTITY_OPTIONS, isUAE,
} from "../../utils/constants";
import {
  PRIORITY_OPTIONS, RISK_OPTIONS, KYC_STATUS_OPTIONS, BLANK_ADDRESS, SECTION_FIELDS,
  buildAccountPayload, buildSectionPatch, validateCoreFields,
} from "./accountForm";
import { useMasters } from "../../hooks/useMasters";
import { selectableCodes } from "../../hooks/masterUtils";

const Section = ({ title, children, hasData, onSave, status, error }) => {
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
              <button type="button" onClick={onSave} disabled={status === "saving"}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-50">
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
export default function AccountFormModal({ initialForm, users, countries, onClose, onChanged, onOpenExisting }) {
  const [form, setForm] = useState(initialForm);
  const [mode, setMode] = useState(initialForm._id ? "edit" : "new");
  const [saving, setSaving] = useState(false);
  const [sectionStatus, setSectionStatus] = useState({});
  const [sectionError, setSectionError] = useState({});

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

  const save = async () => {
    // Industry is only enforced when creating a client, so older records without one can still be edited.
    const invalid = mode === "new" ? validateCoreFields(form) : (!form.company_name?.trim() && "Company name is required");
    if (invalid) return toast.error(invalid);
    try {
      setSaving(true);
      const payload = buildAccountPayload(form);
      if (mode === "edit") await accountsApi.update(form._id, payload);
      else await accountsApi.create(payload);
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
    try {
      const patch = buildSectionPatch(form, SECTION_FIELDS[key]);
      if (form._id) {
        const updated = await accountsApi.update(form._id, patch);
        setForm((f) => ({ ...f, next_aml_review_date: updated.next_aml_review_date }));
      } else {
        if (!isCore) throw new Error("Save Client Info first.");
        const invalid = validateCoreFields(form);
        if (invalid) throw new Error(invalid);
        const created = await accountsApi.create(patch);
        setForm((f) => ({ ...f, _id: created.id }));
        setMode("edit");
      }
      setSectionStatus((s) => ({ ...s, [key]: "saved" }));
      onChanged();
      setTimeout(() => setSectionStatus((s) => (s[key] === "saved" ? { ...s, [key]: "idle" } : s)), 2500);
    } catch (e) {
      setSectionStatus((s) => ({ ...s, [key]: "error" }));
      setSectionError((s) => ({ ...s, [key]: e.response?.data?.detail || e.message || "Save failed" }));
    }
  };

  const sectionProps = (key) => ({ onSave: () => saveSection(key), status: sectionStatus[key], error: sectionError[key] });
  const today = new Date().toISOString().slice(0, 10);

  return (
    <Modal title={mode === "edit" ? "Edit Client" : "New Client"} onClose={onClose}>
      <div className="space-y-3">
        <Field label="Client Type">
          <Select value={form.account_type} onChange={set("account_type")}>
            <option>Corporate</option>
            <option>Individual</option>
          </Select>
        </Field>
        <Field label={isIndividual ? "Full Name (as per passport) *" : "Company Name *"}>
          <Input value={form.company_name} onChange={set("company_name")} placeholder={isIndividual ? "e.g. John Smith" : "e.g. Al Futtaim Group"} />
        </Field>
        <DuplicateWarning
          name={form.company_name}
          excludeId={form._id}
          checkFn={accountsApi.checkDuplicate}
          active={mode === "new"}
          onSelect={async (id) => onOpenExisting(await accountsApi.get(id))}
        />
        {!isIndividual && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Industry *">
                <Input value={form.industry} onChange={set("industry")} placeholder="e.g. Fintech" />
              </Field>
              <Field label="Country of Incorporation / Registration">
                <CountrySelect value={form.country} onChange={set("country")} countries={countries} />
              </Field>
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
          <Field label="Strategic Priority">
            <Select value={form.strategic_priority} onChange={set("strategic_priority")}>
              {PRIORITY_OPTIONS.map((p) => <option key={p}>{p}</option>)}
            </Select>
          </Field>
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
          <Field label="Anchor Entity">
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
              <Input value={form.license_number} onChange={set("license_number")} placeholder="e.g. DIFC-LIC-9012" />
            </Field>
            <Field label="Incorporation Date">
              <Input type="date" max={today} value={form.incorporation_date || ""} onChange={set("incorporation_date")} />
            </Field>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Risk Rating">
            <Select value={form.risk_rating || ""} onChange={set("risk_rating")}>
              <option value="">— Not set —</option>
              {RISK_OPTIONS.map((r) => <option key={r}>{r}</option>)}
            </Select>
          </Field>
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
          <button type="button" onClick={() => saveSection("core", true)} disabled={sectionStatus.core === "saving"}
            className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600 disabled:opacity-50">
            {sectionStatus.core === "saving" ? "Saving…" : "Save Client Info"}
          </button>
          {sectionStatus.core === "saved" && <span className="text-xs text-emerald-600">Saved</span>}
          {sectionStatus.core === "error" && <span className="text-xs text-red-600">{sectionError.core || "Save failed"}</span>}
          {!form._id && <span className="text-xs text-gray-400">Save this first to unlock the sections below</span>}
        </div>

        {!isIndividual && (
          <>
            <Section title="Licensing & Regulatory" hasData={!!(form.licensing_authority || form.license_activities || form.license_start_date || form.license_expiry_date || form.is_regulated || form.license_category)}
              {...sectionProps("licensing")}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Licensing Authority">
                  <Input value={form.licensing_authority} onChange={set("licensing_authority")} placeholder="e.g. DIFC, ADGM, DED" />
                </Field>
                <Field label="License Start Date"><Input type="date" value={form.license_start_date || ""} onChange={set("license_start_date")} /></Field>
                <Field label="License Expiry Date"><Input type="date" min={today} value={form.license_expiry_date || ""} onChange={set("license_expiry_date")} /></Field>
              </div>
              <div className="mb-3">
                <Field label="License Activities">
                  <Textarea rows={3} value={form.license_activities} onChange={set("license_activities")} />
                </Field>
              </div>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                <input type="checkbox" checked={!!form.is_regulated} onChange={setChecked("is_regulated")} /> Is entity regulated
              </label>
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
                  <Field label="License Category"><Input value={form.license_category} onChange={set("license_category")} /></Field>
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
                <Field label="TRN / VAT Registration No."><Input value={form.trn_vat_number} onChange={set("trn_vat_number")} maxLength={15} /></Field>
                <Field label="Financial Year End (MM-DD)"><Input value={form.financial_year_end} onChange={set("financial_year_end")} placeholder="12-31" /></Field>
              </div>
              <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
                <input type="checkbox" checked={!!form.corp_tax_registered} onChange={setChecked("corp_tax_registered")} /> Corporate Tax Registered
              </label>
              {form.corp_tax_registered && (
                <Field label="Corp Tax Registration No. / TAN"><Input value={form.corp_tax_registration_number} onChange={set("corp_tax_registration_number")} maxLength={15} /></Field>
              )}
            </Section>
          </>
        )}

        {isIndividual && (
          <Section title="Individual Details" hasData={!!(form.date_of_birth || form.country_of_birth || form.nationality || form.passport_number || form.occupation || form.individual_mobile_number || form.individual_email || form.country_of_residence || form.source_of_funds || form.source_of_wealth || form.is_pep || (form.nature_of_services_sought || []).length > 0)}
            {...sectionProps("individual")}>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Date of Birth"><Input type="date" value={form.date_of_birth || ""} onChange={set("date_of_birth")} /></Field>
              <Field label="Country of Birth"><CountrySelect value={form.country_of_birth} onChange={set("country_of_birth")} countries={countries} /></Field>
              <Field label="Nationality"><CountrySelect value={form.nationality} onChange={set("nationality")} countries={countries} /></Field>
              <Field label="Passport Number"><Input value={form.passport_number} onChange={set("passport_number")} /></Field>
              <Field label="Passport Expiry"><Input type="date" value={form.passport_expiry_date || ""} onChange={set("passport_expiry_date")} /></Field>
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
            <Field label="Nature of Services Sought">
              <MultiSelect options={selectableCodes(services.items, form.nature_of_services_sought)} value={form.nature_of_services_sought} onChange={setValue("nature_of_services_sought")} />
            </Field>

            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-3 mb-1.5">Residential Address</p>
            <AddressFields value={form.residential_address} onChange={setValue("residential_address")} />

            {isUAE(form.country_of_residence) && (
              <div className="grid grid-cols-2 gap-3 mt-3">
                <Field label="UAE Visa No."><Input value={form.uae_visa_number} onChange={set("uae_visa_number")} /></Field>
                <Field label="UAE Visa Expiry"><Input type="date" value={form.uae_visa_expiry || ""} onChange={set("uae_visa_expiry")} /></Field>
              </div>
            )}

            <label className="flex items-center gap-2 text-xs text-gray-700 mt-3">
              <input type="checkbox" checked={!!form.is_pep} onChange={setChecked("is_pep")} /> Politically Exposed Person (PEP)
            </label>
          </Section>
        )}

        <Section title="Introducer" hasData={!!form.has_introducer} {...sectionProps("introducer")}>
          <label className="flex items-center gap-2 text-xs text-gray-700 mb-3">
            <input type="checkbox" checked={!!form.has_introducer} onChange={setChecked("has_introducer")} /> Introduced by a third party
          </label>
          {form.has_introducer && (
            <Field label="Introducer Name"><Input value={form.introducer_name} onChange={set("introducer_name")} /></Field>
          )}
        </Section>

        <Section title="Services Obtained" hasData={(form.services_obtained || []).length > 0} {...sectionProps("services")}>
          <MultiSelect options={selectableCodes(services.items, form.services_obtained)} value={form.services_obtained} onChange={setValue("services_obtained")} />
        </Section>

        <Section title="Profile Status & Engagement" hasData={form.profile_status !== "New" || !!form.engagement_letter_signed || !!form.engagement_letter_valid_until}
          {...sectionProps("profileStatus")}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Profile Status">
              <Select value={form.profile_status} onChange={set("profile_status")}>
                {PROFILE_STATUS_OPTIONS.map((s) => <option key={s}>{s}</option>)}
              </Select>
            </Field>
            <Field label="Engagement Letter Valid Until"><Input type="date" value={form.engagement_letter_valid_until || ""} onChange={set("engagement_letter_valid_until")} /></Field>
          </div>
          <label className="flex items-center gap-2 text-xs text-gray-700">
            <input type="checkbox" checked={!!form.engagement_letter_signed} onChange={setChecked("engagement_letter_signed")} /> Engagement Letter Signed
          </label>
        </Section>

        <Section title="AML Classification" hasData={!!(form.aml_classification || form.cdd_completion_date)} {...sectionProps("aml")}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="AML Classification">
              <Select value={form.aml_classification || ""} onChange={set("aml_classification")}>
                <option value="">— select —</option>
                {AML_CLASSIFICATION_OPTIONS.map((o) => <option key={o}>{o}</option>)}
              </Select>
            </Field>
            <Field label="CDD Completion Date"><Input type="date" value={form.cdd_completion_date || ""} onChange={set("cdd_completion_date")} /></Field>
          </div>
          {form.aml_classification === "EDD" && (
            <Field label="Reason for EDD"><Input value={form.edd_reason} onChange={set("edd_reason")} maxLength={25} /></Field>
          )}
          {form.next_aml_review_date && (
            <p className="text-xs text-gray-400">Next AML Review Date: <span className="font-medium text-gray-600">{fmtDate(form.next_aml_review_date)}</span> (auto-calculated from Risk Rating + CDD Completion Date)</p>
          )}
        </Section>
      </div>
      <div className="flex justify-end gap-3 mt-5">
        <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={save} disabled={saving}
          className="px-4 py-2 text-sm text-white rounded-lg font-medium disabled:opacity-50"
          style={{ background: "#1a3a5c" }}>
          {saving ? "Saving..." : mode === "edit" ? "Save Changes" : "Create Client"}
        </button>
      </div>
    </Modal>
  );
}
