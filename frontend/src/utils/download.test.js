import { describe, it, expect } from "vitest";
import { fileNameOf } from "./download";

describe("fileNameOf", () => {
  it("uses the name the server gave", () => {
    expect(fileNameOf({ "content-disposition": 'attachment; filename="triam-call-report-ACT-0036-acme-20261124.pdf"' }, "x.pdf"))
      .toBe("triam-call-report-ACT-0036-acme-20261124.pdf");
    expect(fileNameOf({ "content-disposition": "attachment; filename*=UTF-8''triam%20report.xlsx" }, "x")).toBe("triam report.xlsx");
  });
  it("falls back only when the server named none", () => {
    expect(fileNameOf({}, "report.pdf")).toBe("report.pdf");
  });
});
