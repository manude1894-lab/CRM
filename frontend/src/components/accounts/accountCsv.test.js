import { describe, it, expect } from "vitest";
import { parseCSV, parseImportRows, buildAccountsCsv, EXPORT_HEADERS } from "./accountCsv";

const users = [
  { id: 1, name: "Alice RM", role: "rm" },
  { id: 2, name: "Bob RM", role: "rm" },
];

describe("parseCSV", () => {
  it("maps known headers to account fields and ignores unknown ones", () => {
    const rows = parseCSV("Company Name,Industry,Mystery Column\nAcme,Fintech,ignored");
    expect(rows).toEqual([{ company_name: "Acme", industry: "Fintech" }]);
  });

  it("is case-insensitive and trims headers and values", () => {
    expect(parseCSV("  COMPANY NAME ,industry\n  Acme  , Fintech ")).toEqual([{ company_name: "Acme", industry: "Fintech" }]);
  });

  it("handles quoted fields with commas, escaped quotes and newlines", () => {
    const rows = parseCSV('Company Name,Key Contacts\n"Acme, Inc.","Jane ""JD"" Doe\nCEO"');
    expect(rows).toEqual([{ company_name: "Acme, Inc.", key_contacts: 'Jane "JD" Doe\nCEO' }]);
  });

  it("handles CRLF line endings and skips blank lines", () => {
    expect(parseCSV("Company Name\r\nAcme\r\n\r\nBeta\r\n")).toEqual([{ company_name: "Acme" }, { company_name: "Beta" }]);
  });

  it("splits semicolon lists", () => {
    const [row] = parseCSV('Company Name,Services Obtained,Non-anchor Entities\nAcme,"Formation; Accounting ;",A;B');
    expect(row.services_obtained).toEqual(["Formation", "Accounting"]);
    expect(row.non_anchor_entities).toEqual(["A", "B"]);
  });

  it("parses booleans from yes/true/1", () => {
    const [row] = parseCSV("Company Name,Is Regulated,Has Introducer,Corp Tax Registered\nAcme,Yes,no,1");
    expect(row).toMatchObject({ is_regulated: true, has_introducer: false, corp_tax_registered: true });
  });

  it("nests address columns", () => {
    const [row] = parseCSV("Company Name,Registered Address Line 1,Registered Address City,Operating Address P.O. Box\nAcme,1 Main St,Dubai,123");
    expect(row.registered_address).toEqual({ line1: "1 Main St", city: "Dubai" });
    expect(row.operating_address).toEqual({ po_box: "123" });
  });

  it("returns [] for empty input", () => {
    expect(parseCSV("")).toEqual([]);
  });
});

describe("parseImportRows", () => {
  it("drops rows without a company name", () => {
    expect(parseImportRows("Company Name,Industry\n,Fintech\nAcme,Fintech", users)).toEqual([{ company_name: "Acme", industry: "Fintech" }]);
  });

  it("resolves anchor and non-anchor RM names to ids, case-insensitively", () => {
    const [row] = parseImportRows("Company Name,Anchor RM (SPOC),Non-anchor RMs\nAcme,alice rm,Bob RM; Unknown", users);
    expect(row).toEqual({ company_name: "Acme", spoc_id: 1, non_anchor_rm_ids: [2] });
  });

  it("accepts the legacy SPOC header and leaves unknown names unset", () => {
    expect(parseImportRows("Company Name,SPOC\nAcme,Bob RM", users)[0].spoc_id).toBe(2);
    expect(parseImportRows("Company Name,SPOC\nAcme,Nobody", users)[0]).not.toHaveProperty("spoc_id");
  });
});

describe("buildAccountsCsv", () => {
  const account = {
    account_uid: "C-1", account_type: "Corporate", company_name: 'Acme "Holdings", Ltd', industry: "Fintech",
    spoc_id: 1, non_anchor_rm_ids: [2], services_obtained: ["Formation", "Accounting"],
    registered_address: { line1: "1 Main St", city: "Dubai" }, is_regulated: true,
  };

  it("writes one header row plus one row per account, all with the same width", () => {
    const lines = buildAccountsCsv([account, { company_name: "Beta" }], users).split("\n");
    expect(lines).toHaveLength(3);
    const widths = parseRaw(lines.join("\n")).map((r) => r.length);
    expect(new Set(widths)).toEqual(new Set([EXPORT_HEADERS.length]));
  });

  it("round-trips through the importer", () => {
    const csv = buildAccountsCsv([account], users);
    const [row] = parseImportRows(csv, users);
    expect(row).toMatchObject({
      company_name: 'Acme "Holdings", Ltd',
      industry: "Fintech",
      spoc_id: 1,
      non_anchor_rm_ids: [2],
      services_obtained: ["Formation", "Accounting"],
      registered_address: { line1: "1 Main St", city: "Dubai" },
      is_regulated: true,
    });
  });
});

// Splits CSV into raw cell arrays (no header mapping) to check column counts.
function parseRaw(text) {
  const rows = [];
  let row = [], field = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { field += '"'; i++; } else if (c === '"') q = false; else field += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else field += c;
  }
  row.push(field); rows.push(row);
  return rows;
}
