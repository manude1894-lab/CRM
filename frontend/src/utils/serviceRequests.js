// BRD §8; Triam 12-11-2026: a client takes service requests once Compliance has approved it (its Client ID
// is issued), without waiting for the Final approval. Same rule as the server's takes_requests.
const SERVICEABLE = ["Approved", "Active", "Inactive", "Marked for Exit"];

export const takesRequests = (account) => !!account
  && (SERVICEABLE.includes(account.profile_status) || (account.profile_status === "Awaiting Approval" && !!account.client_id));

export const NOT_YET_SERVICEABLE = "Service requests open once Compliance has approved the client.";
