import React, { useEffect, useState } from "react";
import { mastersApi } from "../../api/endpoints";
import { invalidateMasters } from "../../hooks/useMasters";
import { suggestEntityCode } from "../../hooks/masterUtils";
import { Icon, ShowDeactivated } from "../ui";
import { toast } from "../../store/toast";

// Admin maintenance of the BRD §18 master lists. Items are deactivated, never deleted,
// so existing records keep their values; the stored code can't be changed after creation.
// Lists whose values apply to particular Triam entities (none ticked = every entity).
const ENTITY_LISTS = ["service", "service_request_type", "service_request_status"];
// Kept in alphabetical order by the system (no manual ordering); matches master_service.ALPHABETICAL_LISTS.
const ALPHABETICAL_LISTS = ["service", "document_category", "service_request_type", "licensing_authority", "tag", "regulator"];


// One Triam-entity chip: filled when on.
const EntityChip = ({ on, title, onClick, children }) => (
  <button type="button" title={title} onClick={onClick}
    className={`text-[10px] px-1.5 py-0.5 rounded border ${on ? "border-brand-600 bg-brand-600 text-white" : "border-gray-200 text-gray-400 hover:border-gray-300"}`}>
    {children}
  </button>
);

export default function MasterDataPanel() {
  const [types, setTypes] = useState([]);
  const [listType, setListType] = useState(null);
  const [items, setItems] = useState([]);
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newCode, setNewCode] = useState("");
  const [codeTouched, setCodeTouched] = useState(false);
  // Triam 22-11-2026: a Triam entity's code is required and short - it is the Client ID prefix (TPTL/00001).
  const isEntityList = listType === "triam_entity";
  const entityCodeOk = !isEntityList || /^[A-Z0-9]{2,6}$/.test(newCode);
  const setLabel = (v) => {
    setNewLabel(v);
    if (isEntityList && !codeTouched) setNewCode(suggestEntityCode(v));
  };
  const [editingId, setEditingId] = useState(null);
  const [editingLabel, setEditingLabel] = useState("");
  const [entities, setEntities] = useState([]);
  useEffect(() => { mastersApi.list("triam_entity").then((r) => setEntities(r.filter((e) => e.is_active))).catch(() => {}); }, []);

  useEffect(() => {
    mastersApi.types().then((t) => { setTypes(t); setListType((cur) => cur || t[0]?.list_type); })
      .catch((e) => toast.error(e.response?.data?.detail || "Failed to load master lists"));
  }, []);

  const load = async () => {
    if (!listType) return;
    setLoading(true);
    try { setItems(await mastersApi.list(listType, true)); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to load list"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [listType]);

  const changed = () => { invalidateMasters(listType); load(); };

  const add = async () => {
    if (!newLabel.trim()) return;
    if (!entityCodeOk) return toast.error("Enter the entity's short code: 2 to 6 letters or digits, e.g. TPTL");
    try {
      await mastersApi.create(listType, { label: newLabel.trim(), code: newCode.trim() || undefined });
      setNewLabel(""); setNewCode(""); setCodeTouched(false); changed();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to add item"); }
  };

  const patch = async (item, data) => {
    try { await mastersApi.update(item.id, data); changed(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to update item"); }
  };

  // Triam entities of several items at once: shown straight away, then saved; on a failure the list reloads.
  const entityCodes = entities.map((e) => e.code);
  const entitiesOf = (item) => item.meta?.entities || [];
  const setEntitiesOf = async (changes) => { // [[item, codes], ...]
    const todo = changes.filter(([item, codes]) => codes.length !== entitiesOf(item).length || codes.some((c) => !entitiesOf(item).includes(c)));
    if (todo.length === 0) return;
    const byId = new Map(todo.map(([item, codes]) => [item.id, entityCodes.filter((c) => codes.includes(c))]));
    setItems((list) => list.map((it) => (byId.has(it.id) ? { ...it, meta: { ...(it.meta || {}), entities: byId.get(it.id) } } : it)));
    try {
      await Promise.all(todo.map(([item]) => mastersApi.update(item.id, { meta: { ...(item.meta || {}), entities: byId.get(item.id) } })));
      invalidateMasters(listType);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to update the Triam entities");
      load();
    }
  };
  // Triam 14-11-2026: the one-time services table, kept on each service.
  const oneTimeOf = (item) => item.meta?.one_time_entities || [];
  const toggleOneTime = async (item, code) => {
    const next = entityCodes.filter((c) => (c === code) !== oneTimeOf(item).includes(c));
    const meta = { ...(item.meta || {}), one_time_entities: next };
    setItems((list) => list.map((it) => (it.id === item.id ? { ...it, meta } : it)));
    try { await mastersApi.update(item.id, { meta }); invalidateMasters(listType); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to update the one-time services"); load(); }
  };
  const toggleEntity = (item, code) =>
    setEntitiesOf([[item, entitiesOf(item).includes(code) ? entitiesOf(item).filter((c) => c !== code) : [...entitiesOf(item), code]]]);
  const allOn = (item) => entityCodes.every((c) => entitiesOf(item).includes(c));
  const toggleAll = (item) => setEntitiesOf([[item, allOn(item) ? [] : entityCodes]]);
  // The "All items" bar: one entity (or every entity) on or off for every item in the list.
  const columnOn = (code) => items.length > 0 && items.every((it) => entitiesOf(it).includes(code));
  const toggleColumn = (code) => {
    const on = columnOn(code);
    setEntitiesOf(items.map((it) => [it, on ? entitiesOf(it).filter((c) => c !== code) : [...new Set([...entitiesOf(it), code])]]));
  };
  const everythingOn = items.length > 0 && items.every(allOn);
  const toggleEverything = () => setEntitiesOf(items.map((it) => [it, everythingOn ? [] : entityCodes]));

  const move = (index, delta) => {
    const other = items[index + delta];
    if (!other) return;
    const a = items[index];
    // Swap sort orders; equal orders get spread apart first.
    const ao = a.sort_order === other.sort_order ? a.sort_order + delta : other.sort_order;
    Promise.all([mastersApi.update(a.id, { sort_order: ao }), mastersApi.update(other.id, { sort_order: a.sort_order })])
      .then(changed).catch((e) => toast.error(e.response?.data?.detail || "Failed to reorder"));
  };

  const saveLabel = (item) => {
    if (editingLabel.trim() && editingLabel.trim() !== item.label) patch(item, { label: editingLabel.trim() });
    setEditingId(null);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div className="bg-white rounded-xl border border-gray-100 p-3 shadow-sm h-fit">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide px-2 mb-2">Lists</p>
        {types.map((t) => (
          <button key={t.list_type} onClick={() => setListType(t.list_type)}
            className={`w-full text-left text-sm px-2 py-1.5 rounded-lg ${listType === t.list_type ? "bg-brand-50 text-brand-700 font-medium" : "text-gray-600 hover:bg-gray-50"}`}>
            {t.title}
          </button>
        ))}
      </div>

      <div className="md:col-span-3 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{types.find((t) => t.list_type === listType)?.title}</h3>

        {!loading && ENTITY_LISTS.includes(listType) && items.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 px-2 py-1.5 mb-1 rounded-lg border border-gray-100">
            <span className="text-xs font-medium text-gray-500 mr-2">All items</span>
            <EntityChip on={everythingOn} title="Every Triam entity on every item" onClick={toggleEverything}>All</EntityChip>
            {entities.map((e) => <EntityChip key={e.code} on={columnOn(e.code)} title={e.label} onClick={() => toggleColumn(e.code)}>{e.code}</EntityChip>)}
          </div>
        )}

        {loading ? <p className="text-xs text-gray-400">Loading…</p> : (
          <div className="space-y-1 mb-4">
            {items.length === 0 && <p className="text-xs text-gray-400">No items yet.</p>}
            {items.map((item, i) => (
              <div key={item.id} className={`${!item.is_active && !showInactive ? "hidden" : ""} flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg ${item.is_active ? "bg-gray-50" : "bg-gray-50 opacity-60"}`}>
                <div className={`flex items-center gap-2 min-w-0 flex-1 ${listType === "service" ? "flex-wrap" : ""}`}>
                  {editingId === item.id ? (
                    <input autoFocus value={editingLabel} onChange={(e) => setEditingLabel(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && saveLabel(item)} onBlur={() => saveLabel(item)}
                      className="text-xs border border-gray-200 rounded px-1.5 py-1 flex-1" />
                  ) : (
                    <span className="text-sm text-gray-700 truncate">{item.label}</span>
                  )}
                  {item.code !== item.label && <span className="text-[10px] font-mono text-gray-400 flex-shrink-0">{item.code}</span>}
                  {item.meta?.opens_free_text && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 flex-shrink-0">opens free text</span>}
                  {!item.is_active && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 text-gray-500 flex-shrink-0">Inactive</span>}
                  {ENTITY_LISTS.includes(listType) && (
                    <span className="flex flex-wrap gap-1 ml-2">
                      <EntityChip on={allOn(item)} title="Every Triam entity" onClick={() => toggleAll(item)}>All</EntityChip>
                      {entities.map((e) => (
                        <EntityChip key={e.code} on={entitiesOf(item).includes(e.code)} title={e.label} onClick={() => toggleEntity(item, e.code)}>{e.code}</EntityChip>
                      ))}
                    </span>
                  )}
                  {listType === "service" && (
                    <span className="basis-full flex flex-wrap items-center gap-1" title="One-time service for these Triam entities">
                      <span className="text-[10px] text-amber-700 mr-1">One-time service for</span>
                      {entities.map((e) => (
                        <button key={e.code} type="button" title={`One-time service for ${e.label}`} onClick={() => toggleOneTime(item, e.code)}
                          className={`text-[10px] px-1.5 py-0.5 rounded border ${oneTimeOf(item).includes(e.code) ? "border-amber-500 bg-amber-500 text-white" : "border-gray-200 text-gray-400 hover:border-gray-300"}`}>
                          {e.code}
                        </button>
                      ))}
                    </span>
                  )}
                </div>
                <div className="flex gap-1 flex-shrink-0">
                  {!ALPHABETICAL_LISTS.includes(listType) && <>
                    <button onClick={() => move(i, -1)} disabled={i === 0} title="Move up" className="p-1 rounded hover:bg-gray-100 text-gray-400 disabled:opacity-30">▲</button>
                    <button onClick={() => move(i, 1)} disabled={i === items.length - 1} title="Move down" className="p-1 rounded hover:bg-gray-100 text-gray-400 disabled:opacity-30">▼</button>
                  </>}
                  <button onClick={() => { setEditingId(item.id); setEditingLabel(item.label); }} title="Rename" className="p-1 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600">
                    <Icon name="edit" size={12} />
                  </button>
                  <button onClick={() => patch(item, { is_active: !item.is_active })}
                    className={`px-2 py-0.5 text-[11px] rounded border ${item.is_active ? "border-gray-200 text-gray-500 hover:bg-gray-100" : "border-emerald-200 text-emerald-600 hover:bg-emerald-50"}`}>
                    {item.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mb-3"><ShowDeactivated noun="items" count={items.filter((i) => !i.is_active).length} open={showInactive} onToggle={() => setShowInactive((v) => !v)} /></div>
        <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-100">
          <input value={newLabel} onChange={(e) => setLabel(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder={isEntityList ? "Entity name, e.g. TPTL – Triam Professional & Prof Dev Mgmt LLC" : "New item label"}
            className="flex-1 min-w-48 text-xs border border-gray-200 rounded-lg px-2 py-1.5" />
          <input value={newCode} onKeyDown={(e) => e.key === "Enter" && add()} maxLength={isEntityList ? 6 : undefined}
            onChange={(e) => { setCodeTouched(true); setNewCode(isEntityList ? e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "") : e.target.value); }}
            placeholder={isEntityList ? "Code, e.g. TPTL (required)" : "Code (optional, defaults to the label)"}
            aria-invalid={isEntityList && !!newLabel && !entityCodeOk}
            className={`w-56 text-xs border rounded-lg px-2 py-1.5 ${isEntityList && newLabel && !entityCodeOk ? "border-red-300" : "border-gray-200"}`} />
          <button onClick={add} disabled={!newLabel.trim() || !entityCodeOk} className="px-3 py-1.5 text-xs text-white rounded-lg disabled:opacity-50" style={{ background: "#1a3a5c" }}>Add</button>
        </div>
      </div>
    </div>
  );
}
