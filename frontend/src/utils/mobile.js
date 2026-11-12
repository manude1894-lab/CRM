// Mobile numbers (Triam UAT 12-11-2026): digits only, and never without a country code.

/** Keeps the digits of what was typed or pasted (spaces, dashes and letters are dropped). */
export const digitsOnly = (value) => String(value ?? "").replace(/\D/g, "");

/** An error message for a mobile number and its country code, or null when they are fine. */
export function mobileProblem(code, number, label = "Contact Mobile") {
  const n = String(number ?? "").trim();
  if (!n) return null;
  if (!/^\d+$/.test(n)) return `${label}: digits only`;
  if (n.length < 6) return `${label}: enter at least 6 digits`;
  if (!code) return `${label}: select the country code`;
  return null;
}
