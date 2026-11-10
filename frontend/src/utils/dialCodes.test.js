import { describe, it, expect } from "vitest";
import { DIAL_CODES, dialCodeForCountry, dialCodeOptions } from "./dialCodes";

const COUNTRIES = [
  { name: "United Arab Emirates (the)", code: "AE" }, { name: "India", code: "IN" }, { name: "British Virgin Islands", code: "VG" },
  { name: "United States of America (the)", code: "US" }, { name: "Canada", code: "CA" }, { name: "Nowhere", code: null },
];

describe("dial codes", () => {
  it("finds the code for a country name", () => {
    expect(dialCodeForCountry("India", COUNTRIES)).toBe("+91");
    expect(dialCodeForCountry("British Virgin Islands", COUNTRIES)).toBe("+1284");
    expect(dialCodeForCountry("United Arab Emirates (the)", COUNTRIES)).toBe("+971");
  });
  it("gives nothing for an unknown country or one without an ISO code", () => {
    expect(dialCodeForCountry("Atlantis", COUNTRIES)).toBeNull();
    expect(dialCodeForCountry("Nowhere", COUNTRIES)).toBeNull();
    expect(dialCodeForCountry("India", [])).toBeNull();
  });
  it("lists UAE first and one option per code", () => {
    const options = dialCodeOptions(COUNTRIES);
    expect(options[0]).toEqual({ code: "+971", label: "+971 (United Arab Emirates)" });
    expect(options.filter((o) => o.code === "+1")).toEqual([{ code: "+1", label: "+1 (United States of America, Canada)" }]);
  });
  it("uses the ISD code Admin keeps on the Country master (Triam UAT 11-11-2026)", () => {
    const edited = COUNTRIES.map((c) => (c.code === "IN" ? { ...c, dial_code: "+9199" } : c));
    expect(dialCodeForCountry("India", edited)).toBe("+9199");
    expect(dialCodeOptions(edited).some((o) => o.code === "+9199")).toBe(true);
    expect(dialCodeForCountry("Nowhere", [{ name: "Nowhere", code: null, dial_code: "+888" }])).toBe("+888");
  });
  it("falls back when the master isn't loaded", () => {
    const fallback = [{ code: "+971", label: "+971 (UAE)" }];
    expect(dialCodeOptions([], fallback)).toBe(fallback);
  });
  it("every code is a plus and digits", () => {
    expect(Object.values(DIAL_CODES).every((c) => /^\+\d{1,4}$/.test(c))).toBe(true);
  });
});
