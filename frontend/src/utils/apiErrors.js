// FastAPI returns field-format errors (HTTP 422) as a list of objects; screens show `detail`
// directly, which would print "[object Object]". Turn the list into one readable sentence.
import { fieldLabel } from "./auditFormat";

export function formatValidationDetail(detail) {
  if (!Array.isArray(detail)) return detail;
  return detail
    .map((d) => {
      const loc = (d?.loc || []).filter((p) => p !== "body" && typeof p === "string");
      const field = loc.length ? fieldLabel(loc[loc.length - 1]) : "";
      const msg = String(d?.msg || "is invalid").replace(/^Value error, /, "");
      return field ? `${field}: ${msg}` : msg;
    })
    .join("; ");
}
