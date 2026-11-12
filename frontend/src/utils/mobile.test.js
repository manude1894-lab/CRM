import { describe, expect, it } from "vitest";
import { digitsOnly, mobileProblem } from "./mobile";

describe("mobile numbers", () => {
  it("keeps digits only", () => {
    expect(digitsOnly("50a 123-45b67")).toBe("501234567");
    expect(digitsOnly(null)).toBe("");
  });
  it("needs digits, at least 6, and a country code", () => {
    expect(mobileProblem("+971", "501234567")).toBeNull();
    expect(mobileProblem("", "")).toBeNull();
    expect(mobileProblem("+971", "50abc")).toMatch(/digits only/);
    expect(mobileProblem("+971", "123")).toMatch(/at least 6/);
    expect(mobileProblem("", "501234567")).toMatch(/select the country code/);
  });
});
