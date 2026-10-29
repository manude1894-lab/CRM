import React, { useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Modal, Field, Input } from "./ui";

/**
 * Triam 29-10-2026 — a person has one login per role. Signed in with one, they switch to another of their
 * logins here: its email is filled in, they enter that login's password. Cancel keeps the current session.
 */
export default function SwitchLoginModal({ login, onClose, onSwitched }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const signIn = async () => {
    if (!password) return setError("Enter the password for this login");
    setBusy(true); setError(null);
    try {
      const data = await authApi.login(login.email, password);
      useAuthStore.getState().setTokens(data.access_token, data.refresh_token, data.user, data.password_change_recommended);
      onSwitched(data.user);
    } catch (e) {
      setError(e.response?.data?.detail || "Sign-in failed");
    } finally { setBusy(false); }
  };

  return (
    <Modal title={`Sign in as ${login.role_name || "another role"}`} onClose={onClose}>
      <Field label="Email"><Input value={login.email} disabled /></Field>
      <Field label="Password" required>
        <Input type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && signIn()} />
      </Field>
      {error && <p className="text-xs text-red-600 mb-2">{error}</p>}
      <p className="text-[11px] text-gray-500 mb-3">You leave your current login; its work stays as it is.</p>
      <div className="flex justify-end gap-3">
        <button onClick={onClose} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button onClick={signIn} disabled={busy} className="px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50" style={{ background: "#1a3a5c" }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </div>
    </Modal>
  );
}
