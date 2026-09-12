import React, { useEffect, useState } from "react";
import { feedbackApi } from "../api/endpoints";
import { Select, Textarea } from "./ui";
import { FEEDBACK_CHANNEL_OPTIONS } from "../utils/constants";

/**
 * Staff-logged client feedback for a single instruction — not a client-facing form.
 *
 * props:
 *   caseId        — required
 *   instructionId — required
 */
export default function FeedbackPanel({ caseId, instructionId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [rating, setRating] = useState(5);
  const [receivedVia, setReceivedVia] = useState("Email");
  const [comments, setComments] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try { setItems(await feedbackApi.list(caseId)); }
    catch { setItems([]); }
    finally { setLoading(false); }
  };
  useEffect(() => { if (caseId) load(); }, [caseId]);

  const filtered = items.filter((f) => f.instruction_id === instructionId);

  const add = async () => {
    setBusy(true);
    try {
      await feedbackApi.create(caseId, {
        instruction_id: instructionId, rating: Number(rating),
        received_via: receivedVia, comments: comments || null,
      });
      setComments("");
      load();
    } catch (e) {
      alert(e.response?.data?.detail || "Failed to save feedback");
    } finally { setBusy(false); }
  };

  const remove = async (id) => {
    if (!confirm("Remove this feedback entry?")) return;
    try { await feedbackApi.remove(id); load(); }
    catch (e) { alert(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className="space-y-2">
      {!loading && filtered.length === 0 && <p className="text-xs text-gray-400">No feedback logged for this instruction yet.</p>}
      {filtered.map((f) => (
        <div key={f.id} className="flex items-start justify-between gap-2 bg-gray-50 rounded-lg p-2">
          <div>
            <div className="text-xs font-medium text-gray-700">
              {"★".repeat(f.rating || 0)}{"☆".repeat(5 - (f.rating || 0))}
              <span className="text-gray-400 font-normal ml-2">{f.received_via} · {f.feedback_date}</span>
            </div>
            {f.comments && <div className="text-xs text-gray-600 mt-0.5">{f.comments}</div>}
          </div>
          <button onClick={() => remove(f.id)} className="text-xs text-gray-400 hover:text-red-500 flex-shrink-0">✕</button>
        </div>
      ))}

      <div className="flex gap-2 items-start">
        <Select value={rating} onChange={(e) => setRating(e.target.value)}>
          {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} ★</option>)}
        </Select>
        <Select value={receivedVia} onChange={(e) => setReceivedVia(e.target.value)}>
          {FEEDBACK_CHANNEL_OPTIONS.map((o) => <option key={o}>{o}</option>)}
        </Select>
        <Textarea value={comments} onChange={(e) => setComments(e.target.value)} placeholder="What did the client say?" />
        <button type="button" onClick={add} disabled={busy}
          className="text-xs px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex-shrink-0">
          Add
        </button>
      </div>
    </div>
  );
}
