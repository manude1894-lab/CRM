import { describe, it, expect } from "vitest";
import { fieldLabel, formatValue, changeLines, formatTimestamp } from "./auditFormat";

describe("auditFormat", () => {
  it("labels fields", () => {
    expect(fieldLabel("spoc_id")).toBe("Anchor RM");
    expect(fieldLabel("license_expiry_date")).toBe("License expiry date");
  });

  it("formats values for people, dates as DD MM YYYY", () => {
    expect(formatValue(null)).toBe("—");
    expect(formatValue(true)).toBe("Yes");
    expect(formatValue(["A", "B"])).toBe("A, B");
    expect(formatValue("2026-10-04")).toBe("04 10 2026");
    expect(formatValue({ city: "Dubai", zip: "" })).toBe("City: Dubai");
  });

  it("lists before/after for updates", () => {
    const lines = changeLines({ action: "update", changes: { risk_rating: ["Low", "High"], is_pep: [false, true] } });
    expect(lines).toEqual([
      { field: "Risk rating", from: "Low", to: "High" },
      { field: "PEP", from: "No", to: "Yes" },
    ]);
  });

  it("lists initial values for creates and nothing for deletes", () => {
    expect(changeLines({ action: "create", changes: { company_name: "Acme" } })).toEqual([{ field: "Name", from: null, to: "Acme" }]);
    expect(changeLines({ action: "delete", changes: null })).toEqual([]);
  });

  it("formats timestamps as DD MM YYYY HH:MM", () => {
    expect(formatTimestamp("2026-10-04T09:05:00")).toBe("04 10 2026 09:05");
    expect(formatTimestamp("")).toBe("");
  });
});
