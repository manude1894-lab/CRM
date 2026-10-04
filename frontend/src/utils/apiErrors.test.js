import { describe, it, expect } from "vitest";
import { formatValidationDetail } from "./apiErrors";

describe("formatValidationDetail", () => {
  it("leaves plain string details alone", () => {
    expect(formatValidationDetail("Access denied")).toBe("Access denied");
  });

  it("turns FastAPI 422 lists into one sentence", () => {
    const detail = [
      { loc: ["body", "trn_vat_number"], msg: "Value error, must contain digits only" },
      { loc: ["body", "license_category"], msg: "String should have at most 25 characters" },
    ];
    expect(formatValidationDetail(detail)).toBe(
      "TRN / VAT No.: must contain digits only; License category: String should have at most 25 characters",
    );
  });

  it("copes with odd shapes", () => {
    expect(formatValidationDetail([{ msg: "Something broke" }])).toBe("Something broke");
    expect(formatValidationDetail([{ loc: ["body", "rows", 0, "company_name"], msg: "Field required" }])).toBe("Name: Field required");
  });
});
