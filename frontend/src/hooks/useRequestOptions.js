import { useEffect, useState } from "react";
import { instructionsApi } from "../api/endpoints";

// Service request types and statuses depend on the Triam entity handling the request (Triam's
// "Service Requests – Triam Entities" list, kept in Master Data). One request per entity per page load.
const cache = new Map(); // entity code ("" = none) -> Promise<{ types, statuses }>

function load(entity) {
  const key = entity || "";
  if (!cache.has(key)) {
    cache.set(key, instructionsApi.options(key || undefined).catch((e) => { cache.delete(key); throw e; }));
  }
  return cache.get(key);
}

export const EMPTY_OPTIONS = { types: [], statuses: [] };

/** Options for each entity in `entities`: { [entity]: { types: [code], statuses: [{ code, closed }] } }. */
export function useRequestOptions(entities) {
  const [byEntity, setByEntity] = useState({});
  const key = [...new Set(entities.map((e) => e || ""))].sort().join("|");
  useEffect(() => {
    let alive = true;
    key.split("|").forEach((e) => {
      load(e).then((opts) => { if (alive) setByEntity((m) => (m[e] ? m : { ...m, [e]: opts })); }).catch(() => {});
    });
    return () => { alive = false; };
  }, [key]);
  return (entity) => byEntity[entity || ""] || EMPTY_OPTIONS;
}

/** Statuses a user can pick (Dropped is set only through Cancel, with a reason). */
export const pickableStatuses = (opts, current) => {
  const codes = opts.statuses.map((s) => s.code).filter((c) => c !== "Dropped");
  return current && !codes.includes(current) && current !== "Dropped" ? [current, ...codes] : codes;
};
export const firstOpenStatus = (opts) => opts.statuses.find((s) => !s.closed)?.code || "";
export const requestLabel = (r) => (r.instruction_type === "Other" && r.other_description ? `Other – ${r.other_description}` : r.instruction_type);
export const clientEntities = (account) => (account ? [account.anchor_entity, ...(account.non_anchor_entities || [])].filter(Boolean) : []);
