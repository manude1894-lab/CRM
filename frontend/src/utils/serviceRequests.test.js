import { describe, expect, it } from "vitest";
import { takesRequests } from "./serviceRequests";

// Triam 12-11-2026: service requests open once Compliance has approved the client (its Client ID is issued).
describe("takesRequests", () => {
  it("opens after Compliance approval, before the Final approval", () => {
    expect(takesRequests({ profile_status: "Awaiting Approval", client_id: "TABL/00005" })).toBe(true);
  });
  it("stays closed while the client is with Compliance or the RM", () => {
    expect(takesRequests({ profile_status: "Awaiting Approval", client_id: null })).toBe(false);
    for (const status of ["New", "WIP", "Rejected", "Exited"]) expect(takesRequests({ profile_status: status, client_id: "X/1" })).toBe(false);
  });
  it("is open for approved and serviced clients", () => {
    for (const status of ["Approved", "Active", "Inactive", "Marked for Exit"]) expect(takesRequests({ profile_status: status })).toBe(true);
  });
});
