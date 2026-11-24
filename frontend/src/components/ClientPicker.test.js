import { describe, it, expect } from "vitest";
import { matchClients, clientRef } from "./ClientPicker";

const clients = [
  { id: 1, company_name: "52 Summit Capital Limited", client_id: "TCPL/00002" },
  { id: 2, company_name: "abc India ltd", client_id: "TMCL/00017" },
  { id: 3, company_name: "AROMA REAL ESTATE LLC", client_id: "IFZA/00002" },
  { id: 4, company_name: "Zen Arts", account_uid: "ACC-0040" },
];

describe("matchClients", () => {
  it("lists by name A to Z, ignoring case", () => {
    expect(matchClients(clients, "").map((c) => c.id)).toEqual([1, 2, 3, 4]);
  });
  it("finds by name or Client ID, names that begin with the text first", () => {
    expect(matchClients(clients, "ar").map((c) => c.id)).toEqual([3, 4]); // AROMA starts with it; Zen Arts contains it
    expect(matchClients(clients, "ifza").map((c) => c.id)).toEqual([3]);
    expect(matchClients(clients, "00002").map((c) => c.id)).toEqual([1, 3]);
    expect(matchClients(clients, "ACC-0040").map((c) => c.id)).toEqual([4]);
  });
  it("shows the Client ID, or the temporary ID before approval", () => {
    expect(clientRef(clients[0])).toBe("TCPL/00002");
    expect(clientRef(clients[3])).toBe("ACC-0040");
  });
});
