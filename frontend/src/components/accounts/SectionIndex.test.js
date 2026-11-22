import { describe, it, expect } from "vitest";
import { sectionFor } from "./SectionIndex";

const titles = ["Client info", "Licensing & Regulatory", "Registered Address", "Tax", "Introducer", "Firm Documents",
  "Shareholder / UBO Information", "Engagement", "Customer Risk Assessment / KYC & AML (Compliance)"];

describe("sectionFor", () => {
  it("places each completeness item on the form section that holds it", () => {
    expect(sectionFor("Triam assignment", titles)).toBe("Client info");
    expect(sectionFor("Licensing & Regulatory", titles)).toBe("Licensing & Regulatory");
    expect(sectionFor("Documents", titles)).toBe("Firm Documents");
    expect(sectionFor("Profile Status & Engagement", titles)).toBe("Engagement");
    expect(sectionFor("Customer Risk Assessment / KYC & AML", titles)).toBe("Customer Risk Assessment / KYC & AML (Compliance)");
    expect(sectionFor("Shareholder / UBO Information", titles)).toBe("Shareholder / UBO Information");
  });
  it("finds Tax under Financial Year for offshore clients", () => {
    expect(sectionFor("Tax", ["Client info", "Financial Year"])).toBe("Financial Year");
  });
});
