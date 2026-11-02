import React, { useEffect, useRef, useState } from "react";
import { useAuthStore } from "../store/auth";

export const IDLE_MINUTES = 30;
const WARN_SECONDS = 120;
const ACTIVITY = ["mousemove", "mousedown", "keydown", "wheel", "touchstart", "scroll"];

/** Signs the tab out after IDLE_MINUTES without activity, with a two-minute warning first.
 *  Time is measured by the clock, so a computer that was asleep signs out as soon as it wakes. */
export default function IdleSignOut() {
  const logout = useAuthStore((s) => s.logout);
  const last = useRef(Date.now());
  const [left, setLeft] = useState(null); // seconds left while the warning shows

  useEffect(() => {
    const touch = () => { if (left === null) last.current = Date.now(); };
    ACTIVITY.forEach((e) => window.addEventListener(e, touch, { passive: true, capture: true }));
    const timer = setInterval(() => {
      const remaining = Math.round(IDLE_MINUTES * 60 - (Date.now() - last.current) / 1000);
      if (remaining <= 0) {
        try { sessionStorage.setItem("triam-idle-signout", "1"); } catch { /* storage unavailable */ }
        logout();
      } else setLeft(remaining <= WARN_SECONDS ? remaining : null);
    }, 1000);
    return () => { ACTIVITY.forEach((e) => window.removeEventListener(e, touch, { capture: true })); clearInterval(timer); };
  }, [left === null, logout]);

  if (left === null) return null;
  const stay = () => { last.current = Date.now(); setLeft(null); };
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" style={{ background: "rgba(0,0,0,0.4)" }}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm p-6">
        <h2 className="text-base font-semibold text-gray-800 mb-2">Session about to end</h2>
        <p className="text-sm text-gray-600">
          You will be signed out in {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}.
        </p>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={logout} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50">Sign out</button>
          <button onClick={stay} autoFocus className="px-4 py-2 text-sm text-white rounded-lg" style={{ background: "#1a3a5c" }}>Stay signed in</button>
        </div>
      </div>
    </div>
  );
}
