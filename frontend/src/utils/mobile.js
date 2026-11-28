// Mobile numbers (Triam UAT 12-11-2026, 13-11-2026 row 83): digits only, never without a country code, and the
// length for the country, counted without the code: UAE (+971) 9 digits (mobile) or 8 (landline); Triam 28-11-2026:
// other countries their own length (phoneLengths.json, the same table as the server's), any other 8 to 12. A leading
// 0 is ignored. Same rules on the server: backend/app/schemas/phone.py.
import LENGTHS from "./phoneLengths.json";

export const UAE_CODE = "+971";

/** Keeps the digits of what was typed or pasted (spaces, dashes and letters are dropped). */
export const digitsOnly = (value) => String(value ?? "").replace(/\D/g, "");

/** Why a national number has the wrong length for its country code, or null. */
export function lengthProblem(code, number) {
  const n = String(number ?? "").replace(/^0+/, "");
  if (code === UAE_CODE) return n.length === 8 || n.length === 9 ? null : "a UAE number has 9 digits (mobile, e.g. 501234567) or 8 (landline)";
  const [low, high] = LENGTHS[code] || LENGTHS.default;
  if (n.length >= low && n.length <= high) return null;
  const digits = low === high ? `${low} digits` : `${low} to ${high} digits`;
  return LENGTHS[code] ? `a ${code} number has ${digits}` : `enter ${digits}`;
}

/** An error message for a mobile number and its country code, or null when they are fine. */
export function mobileProblem(code, number, label = "Contact Mobile") {
  const n = String(number ?? "").trim();
  if (!n) return null;
  if (!/^\d+$/.test(n)) return `${label}: digits only`;
  if (!code) return `${label}: select the country code`;
  const length = lengthProblem(code, n);
  return length ? `${label}: ${length}` : null;
}

/** "+971501234567" -> { code: "+971", number: "501234567" }, using the longest of `codes` that starts it. */
export function splitPhone(value, codes) {
  const v = String(value ?? "");
  const code = [...codes].sort((a, b) => b.length - a.length).find((c) => v.startsWith(c)) || "";
  return { code, number: code ? v.slice(code.length) : digitsOnly(v) };
}

/** The prospect's single phone value: code and number together, without a leading 0. */
export const joinPhone = (code, number) => (number ? `${code || ""}${String(number).replace(/^0+/, "")}` : "");
