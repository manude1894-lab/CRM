import { describe, expect, it } from "vitest";
import { personLabel } from "./constants";

describe("personLabel", () => {
  const people = [
    { id: 1, name: "S T Krishna", business_role_name: "Relationship Manager" },
    { id: 2, name: "S T Krishna ", business_role_name: "Sales Manager" },
    { id: 3, name: "Aisha", business_role_name: "Relationship Manager" },
  ];
  it("adds the role only when the name appears twice", () => {
    expect(personLabel(people[0], people)).toBe("S T Krishna (Relationship Manager)");
    expect(personLabel(people[1], people)).toBe("S T Krishna (Sales Manager)");
    expect(personLabel(people[2], people)).toBe("Aisha");
  });
  it("works for dashboard rows keyed by user_id", () => {
    const rows = [{ user_id: 1, name: "Sam", business_role_name: "RM" }, { user_id: 2, name: "Sam", business_role_name: "Sales" }];
    expect(personLabel(rows[1], rows)).toBe("Sam (Sales)");
  });
});
