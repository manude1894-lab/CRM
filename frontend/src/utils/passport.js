// Passport Number (Triam 20-11-2026): letters and digits, 6 to 12; spaces and dashes are dropped and letters
// upper-cased as you type. Same rule as the server's backend/app/schemas/identity.py.
export const MIN_PASSPORT = 6;
export const MAX_PASSPORT = 12;

export const cleanPassport = (v) => (v || "").replace(/[\s-]/g, "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, MAX_PASSPORT);

// Why the number can't be saved, or null. A blank number is fine until Submit, which asks for it.
export const passportProblem = (v) => {
  if (!v) return null;
  return v.length < MIN_PASSPORT ? `A passport number has ${MIN_PASSPORT} to ${MAX_PASSPORT} letters or digits` : null;
};
