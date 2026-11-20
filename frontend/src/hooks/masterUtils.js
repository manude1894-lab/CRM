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

// Services offered by the chosen Triam entities (BRD: "Triam Entity – Services Provided
// Relationship"). A service with no entity list is offered by every entity; with no entity chosen yet,
// every service is shown.
export function servicesForEntities(items = [], entities = []) {
  const chosen = entities.filter(Boolean);
  if (!chosen.length) return items;
  return items.filter((i) => !i.meta?.entities?.length || i.meta.entities.some((e) => chosen.includes(e)));
}

// Triam 14-11-2026: the Admin's one-time services table (Services master, "One-time for" entities).
export const oneTimeEntitiesOf = (item) => item?.meta?.one_time_entities || [];

// The one-time services of the chosen Triam entities (every one-time service while none is chosen).
export function oneTimeServices(items = [], entities = []) {
  const chosen = entities.filter(Boolean);
  return items.filter((i) => oneTimeEntitiesOf(i).length && (!chosen.length || oneTimeEntitiesOf(i).some((e) => chosen.includes(e))));
}

// The Triam entities that offer at least one one-time service: the only ones a one-time client may have.
export const oneTimeEntityCodes = (items = []) =>
  [...new Set(items.filter((i) => i.is_active !== false).flatMap(oneTimeEntitiesOf))];

// Triam 20-11-2026: services chosen that the client's Triam entities don't offer (left over after the entity was
// changed). Same rule as the server's entity_service_problems, which refuses them at Submit.
export function servicesNotOffered(items = [], entities = [], sought = []) {
  if (!entities.filter(Boolean).length) return [];
  const offered = new Set(servicesForEntities(items, entities).map((i) => i.code));
  const known = new Set(items.map((i) => i.code));
  return (sought || []).filter((s) => known.has(s) && !offered.has(s));
}
