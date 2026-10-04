// Pure helpers for admin-managed master lists (BRD §18). No React, no API — unit-tested.

// Fallback lists are plain strings (the old hardcoded constants); turn them into master items.
export const itemsFromStrings = (values = []) =>
  values.map((v, i) => ({ id: `fallback-${i}`, code: v, label: v, sort_order: (i + 1) * 10, is_active: true, meta: null }));

export const sortItems = (items = []) =>
  [...items].sort((a, b) => (a.sort_order - b.sort_order) || a.label.localeCompare(b.label));

// Label for a stored code. Codes not in the list (inactive / legacy) display as themselves.
export const labelOf = (items = [], code) => items.find((i) => i.code === code)?.label ?? code ?? "";

// Selectable codes, plus any value the record already holds that is no longer active —
// so editing an old record never silently drops or hides its current value.
export function selectableCodes(items = [], current) {
  const codes = items.filter((i) => i.is_active !== false).map((i) => i.code);
  const held = Array.isArray(current) ? current : current ? [current] : [];
  for (const v of held) if (v && !codes.includes(v)) codes.push(v);
  return codes;
}

// "Other"-style items open a free-text field (BRD §5 Licensing Authority / Regulator).
export const opensFreeText = (items = [], code) => !!items.find((i) => i.code === code)?.meta?.opens_free_text;
