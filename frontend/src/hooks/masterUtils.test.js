import { describe, it, expect } from "vitest";
import { itemsFromStrings, sortItems, labelOf, selectableCodes, opensFreeText } from "./masterUtils";

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
