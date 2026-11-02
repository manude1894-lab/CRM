import { describe, expect, it } from "vitest";
import { previewKind } from "./preview";

describe("previewKind", () => {
  it("shows PDFs, pictures, Word documents and text in the CRM", () => {
    expect(previewKind("application/pdf", "licence.pdf")).toBe("pdf");
    expect(previewKind("image/jpeg", "passport.jpg")).toBe("image");
    expect(previewKind("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "cdd.docx")).toBe("docx");
    expect(previewKind("text/plain", "notes.txt")).toBe("text");
  });
  it("falls back to the file name when the upload had no type", () => {
    expect(previewKind("application/octet-stream", "Trade Licence.PDF")).toBe("pdf");
    expect(previewKind(null, "photo.png")).toBe("image");
  });
  it("offers download only for files the browser cannot show safely", () => {
    expect(previewKind("text/html", "page.html")).toBe(null);
    expect(previewKind("image/svg+xml", "logo.svg")).toBe(null);
    expect(previewKind("application/vnd.ms-excel", "fees.xls")).toBe(null);
  });
});
