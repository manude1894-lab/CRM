import { describe, it, expect } from "vitest";
import { addDays, yearsBefore, latestAdultBirth, isMinor, later, taxNumber } from "./dateRules";

describe("date rules (Triam 16-11-2026)", () => {
  it("works out the adult cut-off, including 29 February", () => {
    expect(latestAdultBirth("2026-11-16")).toBe("2008-11-16");
    expect(yearsBefore("2024-02-29", 18)).toBe("2006-02-28");
    expect(isMinor("2008-11-16", "2026-11-16")).toBe(false);
    expect(isMinor("2008-11-17", "2026-11-16")).toBe(true);
    expect(isMinor("", "2026-11-16")).toBe(false);
  });
  it("adds days across a month end and picks the later date", () => {
    expect(addDays("2026-11-30", 1)).toBe("2026-12-01");
    expect(later("2026-01-01", "", "2026-11-16")).toBe("2026-11-16");
    expect(later("", null)).toBeUndefined();
  });
  it("keeps tax numbers to letters and digits, and a UAE number to 15 digits", () => {
    expect(taxNumber("gb 123-456", "United Kingdom")).toBe("GB123456");
    expect(taxNumber("TRN1002003004005006", "United Arab Emirates (the)")).toBe("100200300400500");
  });
});
