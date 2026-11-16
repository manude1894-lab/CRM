// Triam 16-11-2026: date and number rules for the client and party forms. The server applies the same rules
// (account_service._assert_date_sanity, account_party_service); the form uses these to limit what can be picked.

export const ADULT_AGE = 18;
export const MAX_AGE = 120;

const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export const isoToday = (now = new Date()) => iso(now);

export function addDays(value, days) {
  const [y, m, d] = value.split("-").map(Number);
  return iso(new Date(y, m - 1, d + days));
}

export function yearsBefore(value, years) {
  const [y, m, d] = value.split("-").map(Number);
  // 29 Feb in a non-leap year becomes 28 Feb.
  const target = new Date(y - years, m - 1, 1);
  const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  return iso(new Date(target.getFullYear(), target.getMonth(), Math.min(d, last)));
}

// Latest date of birth for someone who is already an adult today.
export const latestAdultBirth = (today = isoToday()) => yearsBefore(today, ADULT_AGE);
export const earliestBirth = (today = isoToday()) => yearsBefore(today, MAX_AGE);

export const isMinor = (dob, today = isoToday()) => !!dob && dob > latestAdultBirth(today);

// The later of two ISO dates, ignoring blanks.
export const later = (...dates) => dates.filter(Boolean).sort().at(-1) || undefined;

const isUAE = (country) => /united arab emirates/i.test(country || "") || /^\s*(uae|ae)\s*$/i.test(country || "");

// TRN / VAT and Corp Tax numbers: letters and digits in capitals (a foreign VAT number may start with letters);
// a UAE number is 15 digits.
export function taxNumber(value, country) {
  const clean = (value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  return isUAE(country) ? clean.replace(/\D/g, "").slice(0, 15) : clean.slice(0, 20);
}
export const taxNumberHint = (country) => (isUAE(country) ? "UAE: 15 digits" : "Letters and digits, up to 20");
