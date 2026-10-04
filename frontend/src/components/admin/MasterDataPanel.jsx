import React, { useEffect, useState } from "react";
import { mastersApi } from "../../api/endpoints";
import { invalidateMasters } from "../../hooks/useMasters";
import { Icon } from "../ui";
import { toast } from "../../store/toast";

// Admin maintenance of the BRD §18 master lists. Items are deactivated, never deleted,
// so existing records keep their values; the stored code can't be changed after creation.
export default function MasterDataPanel() {
  const [types, setTypes] = useState([]);
  const [listType, setListType] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newCode, setNewCode] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editingLabel, setEditingLabel] = useState("");

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
    try {
      await mastersApi.create(listType, { label: newLabel.trim(), code: newCode.trim() || undefined });
      setNewLabel(""); setNewCode(""); changed();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to add item"); }
  };

  const patch = async (item, data) => {
    try { await mastersApi.update(item.id, data); changed(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed to update item"); }
  };

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
        <h3 className="text-sm font-semibold text-gray-700 mb-1">{types.find((t) => t.list_type === listType)?.title}</h3>
        <p className="text-xs text-gray-400 mb-3">Deactivate instead of deleting — records that already use a value keep it. The code is what's stored and can't be changed.</p>

        {loading ? <p className="text-xs text-gray-400">Loading…</p> : (
          <div className="space-y-1 mb-4">
            {items.length === 0 && <p className="text-xs text-gray-400">No items yet.</p>}
            {items.map((item, i) => (
              <div key={item.id} className={`flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg ${item.is_active ? "bg-gray-50" : "bg-gray-50 opacity-60"}`}>
                <div className="flex items-center gap-2 min-w-0 flex-1">
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
                </div>
                <div className="flex gap-1 flex-shrink-0">
                  <button onClick={() => move(i, -1)} disabled={i === 0} title="Move up" className="p-1 rounded hover:bg-gray-100 text-gray-400 disabled:opacity-30">▲</button>
                  <button onClick={() => move(i, 1)} disabled={i === items.length - 1} title="Move down" className="p-1 rounded hover:bg-gray-100 text-gray-400 disabled:opacity-30">▼</button>
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

        <div className="flex flex-wrap gap-2 pt-3 border-t border-gray-100">
          <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="New item label" className="flex-1 min-w-48 text-xs border border-gray-200 rounded-lg px-2 py-1.5" />
          <input value={newCode} onChange={(e) => setNewCode(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="Code (optional — defaults to label)" className="w-56 text-xs border border-gray-200 rounded-lg px-2 py-1.5" />
          <button onClick={add} className="px-3 py-1.5 text-xs text-white rounded-lg" style={{ background: "#1a3a5c" }}>Add</button>
        </div>
      </div>
    </div>
  );
}
