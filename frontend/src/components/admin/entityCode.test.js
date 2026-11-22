import { describe, expect, it } from "vitest";
import { suggestEntityCode } from "../../hooks/masterUtils";

// Triam 22-11-2026: a Triam entity's code (the Client ID prefix) is suggested from the start of its name.
describe("suggestEntityCode", () => {
  it("takes the leading code of the name", () => {
    expect(suggestEntityCode("TPTL – Triam Professional & Prof Dev Mgmt LLC")).toBe("TPTL");
    expect(suggestEntityCode("tptl - Triam Professional")).toBe("TPTL");
  });
  it("suggests nothing when the name doesn't start with a code", () => {
    expect(suggestEntityCode("Triam Professional & Prof Dev Mgmt LLC")).toBe("");
    expect(suggestEntityCode("")).toBe("");
  });
});
