import React, { useState } from "react";
import { authApi } from "../api/endpoints";
import { Modal, Field, Input } from "./ui";
import { toast } from "../store/toast";

// Same rules as the server (security_service.password_problem) so the user sees them before saving.
export const passwordProblem = (pw) => {
  if ((pw || "").length < 10) return "At least 10 characters";
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return "Use both letters and numbers";
  return null;
};

export default function ChangePasswordModal({ onClose, onChanged, reason }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const problem = next ? passwordProblem(next) : null;
  const mismatch = confirm && next !== confirm;

  const save = async () => {
    if (passwordProblem(next)) return toast.error(passwordProblem(next));
    if (next !== confirm) return toast.error("The new passwords don't match");
    setBusy(true);
    try {
      await authApi.changePassword(current, next);
      toast.success("Password changed");
      onChanged?.();
      onClose();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not change the password");
    } finally { setBusy(false); }
  };

  return (
    <Modal title="Change password" onClose={onClose}>
      {reason && <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">{reason}</p>}
      <Field label="Current password" required><Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
      <Field label="New password" required>
        <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        <p className={`text-[11px] mt-1 ${problem ? "text-red-600" : "text-gray-400"}`}>{problem || "At least 10 characters, with letters and numbers."}</p>
      </Field>
      <Field label="Repeat new password" required>
        <Input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {mismatch && <p className="text-[11px] mt-1 text-red-600">Doesn't match</p>}
      </Field>
      <div className="flex justify-end gap-3 mt-2">
        <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={save} disabled={busy || !current || !next || !confirm}
          className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50" style={{ background: "#1a3a5c" }}>
          {busy ? "Saving…" : "Change password"}
        </button>
      </div>
    </Modal>
  );
}
