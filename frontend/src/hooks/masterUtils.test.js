import { describe, it, expect } from "vitest";
import { itemsFromStrings, sortItems, labelOf, selectableCodes, opensFreeText, servicesForEntities, oneTimeServices, oneTimeEntityCodes } from "./masterUtils";

const items = [
  { code: "COI", label: "Certificate of Incorporation", sort_order: 20, is_active: true },
  { code: "MOA", label: "MoA", sort_order: 10, is_active: true },
  { code: "Other", label: "Other", sort_order: 30, is_active: true, meta: { opens_free_text: true } },
];

describe("masterUtils", () => {
  it("builds items from fallback strings, in order", () => {
    expect(itemsFromStrings(["A", "B"]).map((i) => [i.code, i.label, i.sort_order])).toEqual([["A", "A", 10], ["B", "B", 20]]);
  });

  it("sorts by sort_order then label", () => {
    expect(sortItems(items).map((i) => i.code)).toEqual(["MOA", "COI", "Other"]);
  });

  it("resolves labels and falls back to the code for unknown values", () => {
    expect(labelOf(items, "COI")).toBe("Certificate of Incorporation");
    expect(labelOf(items, "Legacy")).toBe("Legacy");
    expect(labelOf(items, null)).toBe("");
  });

  it("keeps a record's current value selectable even when it is no longer in the list", () => {
    expect(selectableCodes(items, "TMC")).toEqual(["COI", "MOA", "Other", "TMC"]);
    expect(selectableCodes(items, ["MOA", "OLD"])).toEqual(["COI", "MOA", "Other", "OLD"]);
    expect(selectableCodes(items, "")).toEqual(["COI", "MOA", "Other"]);
  });

  it("hides inactive items unless held", () => {
    const withInactive = [...items, { code: "X", label: "X", sort_order: 1, is_active: false }];
    expect(selectableCodes(withInactive)).not.toContain("X");
    expect(selectableCodes(withInactive, "X")).toContain("X");
  });

  it("knows which items open a free-text field", () => {
    expect(opensFreeText(items, "Other")).toBe(true);
    expect(opensFreeText(items, "MOA")).toBe(false);
  });
});

describe("servicesForEntities", () => {
  const items = [
    { code: "Audit Services", meta: { entities: ["TMCL", "TABL"] } },
    { code: "Set up SPVs", meta: { entities: ["TCDL", "TCPL"] } },
    { code: "Legacy", meta: null },
  ];
  it("shows only the chosen entities' services (plus unmapped ones)", () => {
    expect(servicesForEntities(items, ["TABL"]).map((i) => i.code)).toEqual(["Audit Services", "Legacy"]);
    expect(servicesForEntities(items, ["TCPL", "TMCL"]).map((i) => i.code)).toEqual(["Audit Services", "Set up SPVs", "Legacy"]);
  });
  it("shows everything until an entity is chosen", () => {
    expect(servicesForEntities(items, [""]).length).toBe(3);
  });
});

describe("one-time services (Triam 14-11-2026)", () => {
  const items = [
    { code: "Corporate Tax Registration", is_active: true, meta: { entities: ["IFZA"], one_time_entities: ["TABL"] } },
    { code: "Other Corporate Services", is_active: true, meta: { entities: ["IFZA"], one_time_entities: ["TMCL", "IFZA", "TCPL"] } },
    { code: "Audit Services", is_active: true, meta: { entities: ["TMCL", "TABL"] } },
  ];
  it("offers only the one-time services of the client's Triam entities", () => {
    expect(oneTimeServices(items, ["TABL"]).map((i) => i.code)).toEqual(["Corporate Tax Registration"]);
    expect(oneTimeServices(items, ["TCPL", ""]).map((i) => i.code)).toEqual(["Other Corporate Services"]);
    expect(oneTimeServices(items, []).length).toBe(2);
  });
  it("lists the Triam entities that have one-time services", () => {
    expect(oneTimeEntityCodes(items).sort()).toEqual(["IFZA", "TABL", "TCPL", "TMCL"]);
  });
});
