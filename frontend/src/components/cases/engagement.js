// P6 — engagement routes: how a company comes to Triam.
export const ROUTES = ["Formation", "Existing Entity", "Transfer In"];

export const ROUTE_HELP = {
  Formation: "A new company: the full pipeline from enquiry to licence.",
  "Existing Entity": "A company Triam already services. It is created as Active, and the Filing Calendar is built from its real dates.",
  "Transfer In": "A company moving to Triam from another registered agent: CDD, invoice, then the transfer itself.",
};

export const REGISTERED_AGENTS = ["Vistra", "ILS Fiduciary", "Patton, Moreno & Asvat", "Rosemont", "Other"];

// On the Transfer In route the two application stages mean something different.
const TRANSFER_STAGE_LABEL = {
  "Application Submitted": "Transfer Requested from Previous Agent",
  "License Received": "Transfer Completed",
};

export const stageLabel = (stage, route) => (route === "Transfer In" && TRANSFER_STAGE_LABEL[stage]) || stage;

/** Fields sent with a new case for its route (empty strings → null). */
export const routeFields = (f) => {
  if (!f.engagement_route || f.engagement_route === "Formation") return { engagement_route: "Formation" };
  const v = (k) => (f[k] === "" || f[k] === undefined ? null : f[k]);
  return {
    engagement_route: f.engagement_route, previous_agent: v("previous_agent"), incorporation_date: v("incorporation_date"),
    company_number: v("company_number"), registered_agent: v("registered_agent"),
    last_renewal_date: v("last_renewal_date"), last_esr_date: v("last_esr_date"), last_ar_date: v("last_ar_date"),
  };
};
