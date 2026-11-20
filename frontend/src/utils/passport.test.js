import { describe, expect, it } from "vitest";
import { cleanPassport, passportProblem } from "./passport";

// Triam 20-11-2026: Passport Number, letters and digits, 6 to 12.
describe("passport number", () => {
  it("drops spaces, dashes and other characters and upper-cases letters", () => {
    expect(cleanPassport("n 123-4567")).toBe("N1234567");
    expect(cleanPassport("ab/12.34#56")).toBe("AB123456");
  });
  it("stops at 12 characters", () => {
    expect(cleanPassport("A1234567890123")).toBe("A12345678901");
  });
  it("is too short below 6, and blank is left to Submit", () => {
    expect(passportProblem("A1234")).toMatch(/6 to 12/);
    expect(passportProblem("A12345")).toBeNull();
    expect(passportProblem("")).toBeNull();
  });
});
