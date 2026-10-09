import { describe, it, expect } from "vitest";
import { parseDMY } from "../components/ui";
import { csvDate, fmtToday } from "./constants";
import { buildAccountsCsv, parseCSV } from "../components/accounts/accountCsv";

describe("DD MM YYYY entry (BRD: DD MM YYYY with calendar selection)", () => {
  it("accepts DD MM YYYY typed with or without separators", () => {
    expect(parseDMY("09 10 2026")).toBe("2026-10-09");
    expect(parseDMY("09102026")).toBe("2026-10-09");
    expect(parseDMY("09/10/2026")).toBe("2026-10-09");
  });
  it("rejects impossible or incomplete dates", () => {
    expect(parseDMY("31 02 2026")).toBeNull();
    expect(parseDMY("09 13 2026")).toBeNull();
    expect(parseDMY("09 10 26")).toBeNull();
  });
});

describe("dates written by the system", () => {
  it("top bar reads weekday DD MM YYYY", () => {
    expect(fmtToday(new Date(2026, 9, 9))).toBe("Fri 09 10 2026");
  });
  it("CSV dates are DD/MM/YYYY and timestamps keep the time", () => {
    expect(csvDate("2026-10-09")).toBe("09/10/2026");
    expect(csvDate("2026-10-09T13:45:00Z")).toBe("09/10/2026 13:45");
    expect(csvDate("Fintech")).toBe("Fintech");
  });
  it("a client export imports back with the same dates", () => {
    const csv = buildAccountsCsv([{ company_name: "Acme", incorporation_date: "2019-03-14", license_expiry_date: "2027-03-13" }], []);
    expect(csv).toContain('"14/03/2019"');
    const [row] = parseCSV(csv);
    expect(row).toMatchObject({ incorporation_date: "2019-03-14", license_expiry_date: "2027-03-13" });
  });
});
