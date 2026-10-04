import { describe, it, expect } from "vitest";
import { parseFYE, toFYE, fmtFYE, daysIn } from "./fye";
import { fmtDate } from "./constants";

describe("financial year end", () => {
  it("displays MM-DD as DD-MMM", () => {
    expect(fmtFYE("12-31")).toBe("31-Dec");
    expect(fmtFYE("03-05")).toBe("05-Mar");
    expect(fmtFYE("")).toBe("");
    expect(fmtFYE("legacy text")).toBe("legacy text");
  });

  it("round-trips month and day", () => {
    expect(parseFYE("06-30")).toEqual({ month: "6", day: "30" });
    expect(toFYE("6", "30")).toBe("06-30");
    expect(toFYE("", "30")).toBe("");
  });

  it("clamps the day to the month's length", () => {
    expect(toFYE("4", "31")).toBe("04-30");
    expect(toFYE("2", "31")).toBe("02-29");
    expect(daysIn("2")).toBe(29);
  });
});

describe("fmtDate", () => {
  it("shows DD MM YYYY (BRD §14)", () => {
    expect(fmtDate("2026-10-04")).toBe("04 10 2026");
    expect(fmtDate("2026-10-04T08:00:00Z")).toBe("04 10 2026");
    expect(fmtDate(null)).toBe("");
  });
});
