import { describe, expect, it } from "vitest";
import { digitsOnly, mobileProblem, splitPhone, joinPhone } from "./mobile";

describe("mobile numbers", () => {
  it("keeps digits only", () => {
    expect(digitsOnly("50a 123-45b67")).toBe("501234567");
    expect(digitsOnly(null)).toBe("");
  });
  it("needs digits and a country code", () => {
    expect(mobileProblem("", "")).toBeNull();
    expect(mobileProblem("+971", "50abc")).toMatch(/digits only/);
    expect(mobileProblem("", "501234567")).toMatch(/select the country code/);
  });
  it("UAE: 9 digits for a mobile, 8 for a landline, a leading 0 ignored (Triam UAT 13-11-2026 row 83)", () => {
    expect(mobileProblem("+971", "501234567")).toBeNull();
    expect(mobileProblem("+971", "0501234567")).toBeNull();
    expect(mobileProblem("+971", "43334444")).toBeNull();
    expect(mobileProblem("+971", "5012345")).toMatch(/UAE number has 9 digits/);
    expect(mobileProblem("+971", "5012345678")).toMatch(/UAE number has 9 digits/);
  });
  it("other countries: 8 to 12 digits", () => {
    expect(mobileProblem("+973", "36123456")).toBeNull(); // Bahrain mobile, 8 digits
    expect(mobileProblem("+91", "9876543210")).toBeNull();
    expect(mobileProblem("+44", "1234567")).toMatch(/8 to 12 digits/);
  });
  it("splits and joins a prospect's phone", () => {
    expect(splitPhone("+971501234567", ["+97", "+971", "+1"])).toEqual({ code: "+971", number: "501234567" });
    expect(splitPhone("0501234567", ["+971"])).toEqual({ code: "", number: "0501234567" });
    expect(joinPhone("+971", "0501234567")).toBe("+971501234567");
    expect(joinPhone("+971", "")).toBe("");
  });
});
