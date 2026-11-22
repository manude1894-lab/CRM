import { describe, it, expect } from "vitest";
import { pageNumbers, sortRows, compareValues } from "./listing";

describe("pageNumbers", () => {
  it("shows the ends and the pages around the current one", () => {
    expect(pageNumbers(0, 3)).toEqual([0, 1, 2]);
    expect(pageNumbers(10, 20)).toEqual([0, "…", 8, 9, 10, 11, 12, "…", 19]);
  });
});

describe("sorting", () => {
  const rows = [{ n: "b", d: "2026-01-02", x: 10 }, { n: "A", d: "2025-05-01", x: 9 }, { n: "c", d: null, x: "—" }];
  it("sorts text, dates and numbers, blanks last", () => {
    expect(sortRows(rows, { by: "n", dir: "asc" }, (r, k) => r[k]).map((r) => r.n)).toEqual(["A", "b", "c"]);
    expect(sortRows(rows, { by: "d", dir: "desc" }, (r, k) => r[k]).map((r) => r.n)).toEqual(["b", "A", "c"]);
    expect(sortRows(rows, { by: "x", dir: "asc" }, (r, k) => r[k]).map((r) => r.x)).toEqual([9, 10, "—"]);
  });
  it("compares numbers numerically and IDs naturally", () => {
    expect(compareValues("9", "10")).toBeLessThan(0);
    expect(compareValues("TCPL/00009", "TCPL/00010")).toBeLessThan(0);
  });
});
