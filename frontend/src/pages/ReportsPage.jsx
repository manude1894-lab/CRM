import React from "react";
import { PageHeader } from "../components/ui";
import StandardReports from "../components/reports/StandardReports";

/** BRD §20 — the standard reports, on screen and exported to CSV. Custom reports and favourites follow
 * once Triam gives the details (§20b). */
export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Reports" />
      <StandardReports />
    </div>
  );
}
