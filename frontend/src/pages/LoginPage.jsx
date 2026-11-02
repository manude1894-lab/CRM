import React, { useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Input } from "../components/ui";
import { passwordProblem } from "../components/ChangePasswordModal";

// Opened in a new tab from another of the person's logins: that login's email is handed over through
// local storage (read once, within a minute) so it never appears in the address bar.
const handedOverEmail = (() => {
  try {
    const raw = localStorage.getItem("triam-switch");
    localStorage.removeItem("triam-switch");
    const { email, at } = JSON.parse(raw || "{}");
    return email && Date.now() - at < 60000 ? email : "";
  } catch { return ""; }
})();

// The emailed reset link (/reset-password?token=…): the token is read once and taken out of the address bar.
const resetToken = (() => {
  if (window.location.pathname !== "/reset-password") return "";
  const token = new URLSearchParams(window.location.search).get("token") || "";
  window.history.replaceState(null, "", "/");
  return token;
})();

export default function LoginPage() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const [view, setView] = useState(resetToken ? "reset" : "signin"); // "signin" | "forgot" | "reset"
  const [email, setEmail] = useState(handedOverEmail);
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const show = (next) => { setView(next); setError(""); setNotice(""); setPassword(""); setRepeat(""); };

  const sendLink = async () => {
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Enter your email address");
    setError("");
    setLoading(true);
    try {
      await authApi.forgotPassword(email.trim().toLowerCase());
      setNotice("If the email is registered, a reset link is on its way. Your administrator has also been notified.");
    } catch (e) {
      setError(e.response?.data?.detail || "Could not send the reset link. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const savePassword = async () => {
    if (passwordProblem(password)) return setError(passwordProblem(password));
    if (password !== repeat) return setError("The passwords don't match");
    setError("");
    setLoading(true);
    try {
      await authApi.resetPassword(resetToken, password);
      show("signin");
      setNotice("Password changed. Sign in with your new password.");
    } catch (e) {
      setError(e.response?.data?.detail || "Could not change the password.");
    } finally {
      setLoading(false);
    }
  };

  const submit = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await authApi.login(email.trim().toLowerCase(), password);
      setTokens(data.access_token, data.refresh_token, data.user, !!data.password_change_recommended);
    } catch (e) {
      setError(e.response?.data?.detail || "Login failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Branding panel */}
      <div
        className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 relative overflow-hidden"
        style={{ background: "linear-gradient(135deg, #0f1c2e 0%, #1a3a5c 50%, #0d2b45 100%)" }}
      >
        <div
          className="absolute -top-24 -right-24 w-96 h-96 rounded-full opacity-10"
          style={{ background: "#E8B84B" }}
        />
        <div
          className="absolute -bottom-32 -left-16 w-80 h-80 rounded-full opacity-10"
          style={{ background: "#1a3a5c" }}
        />
        <div className="relative">
          <div className="inline-flex items-center justify-center bg-white rounded-2xl p-5 shadow-xl">
            <img src="/triam-logo.png" alt="TRIAM" className="h-24 w-auto" />
          </div>
        </div>
        <div className="relative">
          <h1 className="text-4xl font-bold text-white leading-tight mb-4 tracking-tight">
            Client Relationship<br />Management
          </h1>
          <p className="text-brand-200 text-base max-w-sm">
            Clients, onboarding, compliance and servicing for the Triam group.
          </p>
        </div>
        <div className="relative flex items-center gap-6 text-brand-200 text-xs">
          <span>© {new Date().getFullYear()} Triam Management Services</span>
        </div>
      </div>

      {/* Sign-in panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-gray-50">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex flex-col items-center mb-8">
            <div className="inline-flex items-center justify-center bg-white rounded-2xl p-4 shadow-md border border-gray-100 mb-3">
              <img src="/triam-logo.png" alt="TRIAM" className="h-20 w-auto" />
            </div>
            <p className="text-gray-500 text-sm">Client Relationship Management</p>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-6">
            {view === "signin" ? "Sign in" : view === "forgot" ? "Reset password" : "Choose a new password"}
          </h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3 mb-4">
              {error}
            </div>
          )}
          {notice && (
            <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-lg px-4 py-3 mb-4">
              {notice}
            </div>
          )}

          {view === "signin" && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value.replace(/\s/g, ""))} autoCapitalize="none" autoCorrect="off" />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-medium text-gray-600">Password</label>
                  <button type="button" onClick={() => show("forgot")} className="text-xs text-brand-600 hover:underline">
                    Forgot password?
                  </button>
                </div>
                <Input
                  type="password"
                  autoFocus={!!handedOverEmail}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && submit()}
                />
              </div>
              <button
                onClick={submit}
                disabled={loading}
                className="w-full text-white font-semibold py-2.5 rounded-lg transition-opacity hover:opacity-90 disabled:opacity-60 shadow-sm"
                style={{ background: "#1a3a5c" }}
              >
                {loading ? "Signing in..." : "Sign In"}
              </button>
            </div>
          )}

          {view === "forgot" && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <Input type="email" value={email} autoFocus onChange={(e) => setEmail(e.target.value.replace(/\s/g, ""))}
                  onKeyDown={(e) => e.key === "Enter" && !notice && sendLink()} autoCapitalize="none" autoCorrect="off" />
              </div>
              {!notice && (
                <button
                  onClick={sendLink}
                  disabled={loading}
                  className="w-full text-white font-semibold py-2.5 rounded-lg transition-opacity hover:opacity-90 disabled:opacity-60 shadow-sm"
                  style={{ background: "#1a3a5c" }}
                >
                  {loading ? "Sending..." : "Send reset link"}
                </button>
              )}
              <button type="button" onClick={() => show("signin")} className="w-full text-sm text-brand-600 hover:underline">
                Back to sign in
              </button>
            </div>
          )}

          {view === "reset" && (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">New password</label>
                <Input type="password" autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
                <p className="text-[11px] mt-1 text-gray-400">At least 10 characters, with letters and numbers.</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Repeat new password</label>
                <Input type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && savePassword()} />
              </div>
              <button
                onClick={savePassword}
                disabled={loading}
                className="w-full text-white font-semibold py-2.5 rounded-lg transition-opacity hover:opacity-90 disabled:opacity-60 shadow-sm"
                style={{ background: "#1a3a5c" }}
              >
                {loading ? "Saving..." : "Save password"}
              </button>
              <button type="button" onClick={() => show("signin")} className="w-full text-sm text-brand-600 hover:underline">
                Back to sign in
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
