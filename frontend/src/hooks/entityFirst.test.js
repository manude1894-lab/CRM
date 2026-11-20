import { describe, it, expect } from "vitest";
import { servicesNotOffered } from "./masterUtils";
import { multiSelectRows } from "../components/ui";

// Triam 20-11-2026: services left over after the client's Triam entity changed are flagged (and refused at Submit).
describe("servicesNotOffered", () => {
  const services = [
    { code: "AUDIT", label: "Audit Services", meta: { entities: ["TCPL"] } },
    { code: "BVI", label: "Offshore Company Formation Services", meta: { entities: ["TBVI"] } },
    { code: "OTHER", label: "Other Corporate Services", meta: {} },
  ];
  it("lists the services the chosen entities don't offer", () => {
    expect(servicesNotOffered(services, ["TCPL"], ["AUDIT", "BVI", "OTHER"])).toEqual(["BVI"]);
    expect(servicesNotOffered(services, ["TCPL", "TBVI"], ["AUDIT", "BVI"])).toEqual([]);
  });
  it("says nothing while no entity is chosen, or for a service no longer in the list", () => {
    expect(servicesNotOffered(services, [""], ["BVI"])).toEqual([]);
    expect(servicesNotOffered(services, ["TCPL"], ["RETIRED"])).toEqual([]);
  });
});

// Triam 20-11-2026: the Non-anchor RMs list gets a search; ticked names come first.
describe("multiSelectRows", () => {
  const names = { 1: "Ruma Isjan", 2: "Ismail Mohd", 3: "Nirmal Suchak", 4: "Sajith Nair" };
  const label = (id) => names[id];
  it("puts the ticked ones first", () => {
    expect(multiSelectRows([1, 2, 3, 4], [3], label, "")).toEqual([3, 1, 2, 4]);
  });
  it("filters by the search text, ignoring case", () => {
    expect(multiSelectRows([1, 2, 3, 4], [], label, "  ISM ")).toEqual([2]);
    expect(multiSelectRows([1, 2, 3, 4], [4], label, "nai")).toEqual([4]);
  });
});
