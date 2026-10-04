// Financial Year End (BRD §5/§14): stored as "MM-DD", displayed as "DD-MMM" (e.g. 31-Dec).

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS_IN_MONTH = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]; // Feb allows 29 (leap years)

export function parseFYE(value) {
  const m = /^(\d{2})-(\d{2})$/.exec(value || "");
  if (!m) return { month: "", day: "" };
  return { month: String(+m[1]), day: String(+m[2]) };
}

export function toFYE(month, day) {
  if (!month || !day) return "";
  const d = Math.min(+day, DAYS_IN_MONTH[+month - 1]);
  return `${String(+month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export function fmtFYE(value) {
  const { month, day } = parseFYE(value);
  if (!month) return value || "";
  return `${day.padStart(2, "0")}-${MONTHS[+month - 1]}`;
}

export const daysIn = (month) => (month ? DAYS_IN_MONTH[+month - 1] : 31);
