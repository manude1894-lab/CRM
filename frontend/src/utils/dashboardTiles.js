// Which dashboard tiles a user sees (review 22-11-2026, package 5): the numbers each desk acts on.
// Administrators and Inquiry & Reports see every tile; someone holding several roles sees the tiles of each.
export const ALL_TILES = ["unassigned", "preparing", "awaiting", "active", "requests", "unpaid", "aml"];

const BY_DESK = {
  approver: ["approver", "compliance", "active", "aml"],
  compliance: ["compliance", "aml", "active", "preparing"],
  accounts: ["toRaise", "unpaid", "overdue", "requests"],
  coordinator: ["unassigned", "preparing", "awaiting"],
  rm: ["preparing", "awaiting", "active", "requests"],
};
const ORDER = ["approver", "compliance", "toRaise", "overdue", "unassigned", "preparing", "awaiting",
  "active", "requests", "unpaid", "aml"];

export function dashboardTiles({ isAdmin, readOnly, coordinator, can, handlesClients }) {
  if (isAdmin || readOnly) return ALL_TILES;
  const desks = [];
  if (can("client.final_approve")) desks.push("approver");
  if (can("client.approve")) desks.push("compliance");
  if (can("invoice.manage")) desks.push("accounts");
  if (coordinator) desks.push("coordinator");
  if (handlesClients && !coordinator) desks.push("rm");
  if (!desks.length) return ALL_TILES;
  const keys = new Set(desks.flatMap((d) => BY_DESK[d]));
  return ORDER.filter((k) => keys.has(k));
}
