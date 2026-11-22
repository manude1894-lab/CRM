import { describe, it, expect } from "vitest";
import { dashboardTiles, ALL_TILES } from "./dashboardTiles";

const user = (perms, extra = {}) => ({ isAdmin: false, readOnly: false, coordinator: false, handlesClients: false,
  can: (f) => perms.includes(f), ...extra });

describe("dashboardTiles", () => {
  it("shows every tile to admins and Inquiry", () => {
    expect(dashboardTiles(user([], { isAdmin: true }))).toEqual(ALL_TILES);
    expect(dashboardTiles(user(["read_only"], { readOnly: true }))).toEqual(ALL_TILES);
  });
  it("gives each desk its own numbers", () => {
    expect(dashboardTiles(user([], { handlesClients: true }))).toEqual(["preparing", "awaiting", "active", "requests"]);
    expect(dashboardTiles(user(["invoice.manage"]))).toEqual(["toRaise", "overdue", "requests", "unpaid"]);
    expect(dashboardTiles(user(["client.final_approve"]))[0]).toBe("approver");
  });
  it("joins the tiles of someone with two roles", () => {
    const t = dashboardTiles(user(["client.approve"], { handlesClients: true }));
    expect(t).toContain("compliance");
    expect(t).toContain("requests");
    expect(new Set(t).size).toBe(t.length);
  });
});
