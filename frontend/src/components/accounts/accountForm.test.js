import { describe, it, expect } from "vitest";
import {
  BLANK_ACCOUNT_FORM, SECTION_FIELDS, accountToForm, cleanPayload,
  buildAccountPayload, buildSectionPatch, validateCoreFields,
} from "./accountForm";

describe("accountToForm", () => {
  it("fills missing values with form defaults and keeps the id", () => {
    const form = accountToForm({ id: 7, company_name: "Acme", strategic_priority: "High", existing_relationship: "Yes" });
    expect(form).toMatchObject({
      _id: 7, company_name: "Acme", account_type: "Corporate", industry: "", kyc_status: "Not Started",
      profile_status: "New", is_regulated: null, services_obtained: [], tags: [], next_aml_review_date: null,
    });
    expect(form.registered_address).toEqual(BLANK_ACCOUNT_FORM.registered_address);
  });

  it("splits the comma-separated tags string into an array", () => {
    expect(accountToForm({ tags: "VIP, Fintech ,," }).tags).toEqual(["VIP", "Fintech"]);
  });

  it("merges partial addresses over the blank address", () => {
    const form = accountToForm({ registered_address: { city: "Dubai" } });
    expect(form.registered_address).toMatchObject({ city: "Dubai", line1: "" });
  });

  it("produces every field the blank form has", () => {
    const form = accountToForm({});
    for (const key of Object.keys(BLANK_ACCOUNT_FORM)) expect(form).toHaveProperty(key);
  });
});

describe("cleanPayload", () => {
  it("turns empty strings into null and leaves other values alone", () => {
    expect(cleanPayload({ a: "", b: "x", c: false, d: 0, e: [] })).toEqual({ a: null, b: "x", c: false, d: 0, e: [] });
  });
});

describe("P1 fields", () => {
  it("maps client ID and status timestamp as read-only header values and never sends them back", () => {
    const form = accountToForm({ id: 1, company_name: "Acme", client_id: "TCPL/00001", status_updated_at: "2026-10-04T10:00:00Z", search_name: "Acme", kyc_verified_by: "Aisha" });
    expect(form._client_id).toBe("TCPL/00001");
    expect(form.search_name).toBe("Acme");
    expect(form.kyc_verified_by).toBe("Aisha");
    const payload = buildAccountPayload(form);
    expect(payload).not.toHaveProperty("_client_id");
    expect(payload).not.toHaveProperty("_status_updated_at");
  });

  it("saves the search name with core info and KYC-verified-by with AML", () => {
    expect(SECTION_FIELDS.core).toContain("search_name");
    expect(SECTION_FIELDS.aml).toContain("kyc_verified_by");
    expect(SECTION_FIELDS.licensing).toContain("licensing_authority_other");
  });
});

describe("buildAccountPayload", () => {
  it("strips client-only fields, joins tags and converts spoc_id to a number", () => {
    const payload = buildAccountPayload({ ...BLANK_ACCOUNT_FORM, _id: 3, next_aml_review_date: "2027-01-01", company_name: "Acme", tags: ["VIP", "New"], spoc_id: "5" });
    expect(payload).not.toHaveProperty("_id");
    expect(payload).not.toHaveProperty("next_aml_review_date");
    expect(payload).toMatchObject({ company_name: "Acme", tags: "VIP, New", spoc_id: 5, industry: null });
  });

  it("sends null for empty tags and spoc", () => {
    expect(buildAccountPayload({ tags: [], spoc_id: "" })).toEqual({ tags: null, spoc_id: null });
  });
});

describe("buildSectionPatch", () => {
  it("only includes the requested fields", () => {
    const form = { ...BLANK_ACCOUNT_FORM, trn_vat_number: "123", company_name: "Acme" };
    expect(buildSectionPatch(form, SECTION_FIELDS.tax)).toEqual({
      trn_vat_number: "123", financial_year_end: null, corp_tax_registered: null, corp_tax_registration_number: null,
    });
  });

  it("converts tags and spoc_id in the core section", () => {
    const patch = buildSectionPatch({ ...BLANK_ACCOUNT_FORM, tags: ["VIP"], spoc_id: "2" }, SECTION_FIELDS.core);
    expect(patch).toMatchObject({ tags: "VIP", spoc_id: 2 });
  });
});

describe("validateCoreFields", () => {
  it("requires a company name", () => {
    expect(validateCoreFields({ company_name: "  ", industry: "x" })).toBe("Company name is required");
  });

  it("requires industry for corporate clients only", () => {
    expect(validateCoreFields({ company_name: "Acme", anchor_entity: "TCPL", account_type: "Corporate", industry: "" })).toBe("Industry is required");
    expect(validateCoreFields({ company_name: "Jane", anchor_entity: "TCPL", account_type: "Individual", industry: "" })).toBeNull();
  });

  it("requires an Anchor Triam Entity (it builds the Client ID)", () => {
    expect(validateCoreFields({ company_name: "Acme", industry: "Fintech" })).toMatch(/Anchor Triam Entity/);
  });
});
