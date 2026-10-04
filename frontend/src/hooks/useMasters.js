import { useEffect, useState } from "react";
import { mastersApi } from "../api/endpoints";
import { itemsFromStrings, sortItems, labelOf } from "./masterUtils";

// One request per list per page load, shared by every component that asks for it.
const cache = new Map(); // listType -> Promise<items>

function load(listType) {
  if (!cache.has(listType)) {
    cache.set(listType, mastersApi.list(listType).then(sortItems).catch((e) => {
      cache.delete(listType); // allow a retry later
      throw e;
    }));
  }
  return cache.get(listType);
}

// Call after an admin edits a list so the next read refetches.
export function invalidateMasters(listType) {
  if (listType) cache.delete(listType); else cache.clear();
}

/**
 * Admin-managed list of values (BRD §18).
 * `fallback` (array of strings) is used until the list loads, and if the API isn't available —
 * so screens keep working against a backend that hasn't been migrated yet.
 */
export function useMasters(listType, fallback = []) {
  const [items, setItems] = useState(() => itemsFromStrings(fallback));
  useEffect(() => {
    let alive = true;
    load(listType).then((rows) => { if (alive && rows.length) setItems(rows); }).catch(() => {});
    return () => { alive = false; };
  }, [listType]);
  return { items, codes: items.map((i) => i.code), labelOf: (code) => labelOf(items, code) };
}
