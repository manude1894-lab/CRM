import React, { useEffect, useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Input } from "../components/ui";
import { PASSWORD_HINT, passwordProblem } from "../components/ChangePasswordModal";
import { IDLE_MINUTES } from "../components/IdleSignOut";

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
let resetToken = (() => {
  if (window.location.pathname !== "/reset-password") return "";
  const token = new URLSearchParams(window.location.search).get("token") || "";
  window.history.replaceState(null, "", "/");
  return token;
})();

const Label = ({ children }) => <label className="block text-xs font-medium text-gray-600 mb-1">{children}</label>;

const PrimaryButton = ({ onClick, busy, busyText, children }) => (
  <button onClick={onClick} disabled={busy} style={{ background: "#1a3a5c" }}
    className="w-full text-white font-semibold py-2.5 rounded-lg transition-opacity hover:opacity-90 disabled:opacity-60 shadow-sm">
    {busy ? busyText : children}
  </button>
);

export default function LoginPage() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const [view, setView] = useState(resetToken ? "reset" : "signin"); // "signin" | "forgot" | "reset"
  const [email, setEmail] = useState(handedOverEmail);
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  // Signed out for inactivity (IdleSignOut): said once, on the sign-in page.
  const [notice, setNotice] = useState(() => {
    try { return sessionStorage.getItem("triam-idle-signout") ? `You were signed out after ${IDLE_MINUTES} minutes without activity.` : ""; }
    catch { return ""; }
  });
  useEffect(() => { try { sessionStorage.removeItem("triam-idle-signout"); } catch { /* storage unavailable */ } }, []);
  // The reset link's token belongs to this sign-in page only: after a later sign-out the page opens on Sign in.
  const [token] = useState(resetToken);
  useEffect(() => { resetToken = ""; }, []);
  const [loading, setLoading] = useState(false);

  const show = (next) => { setView(next); setError(""); setNotice(""); setPassword(""); setRepeat(""); };

  // Each action: clear the error, show progress, and show the server's message if it fails.
  const run = async (fallback, action) => {
    setError("");
    setLoading(true);
    try { await action(); }
    catch (e) { setError(e.response?.data?.detail || fallback); }
    finally { setLoading(false); }
  };

  const submit = () => run("Login failed. Please check your credentials.", async () => {
    const data = await authApi.login(email.trim().toLowerCase(), password);
    setTokens(data.access_token, data.refresh_token, data.user, !!data.password_change_recommended);
  });

  const sendLink = () => {
    if (!/^\S+@\S+\.\S+$/.test(email)) return setError("Enter your email address");
    return run("Could not send the reset link. Please try again.", async () => {
      const { data } = await authApi.forgotPassword(email.trim().toLowerCase());
      setNotice(data?.email_sent
        ? "If the email is registered, a reset link is on its way. Your administrator has also been notified."
        : "Your administrator has been notified and will reset your password.");
    });
  };

  const savePassword = () => {
    if (passwordProblem(password)) return setError(passwordProblem(password));
    if (password !== repeat) return setError("The passwords don't match");
    return run("Could not change the password.", async () => {
      await authApi.resetPassword(token, password);
      show("signin");
      setNotice("Password changed. Sign in with your new password.");
    });
  };

  const emailInput = (props) => (
    <Input type="email" value={email} onChange={(e) => setEmail(e.target.value.replace(/\s/g, ""))}
      autoCapitalize="none" autoCorrect="off" {...props} />
  );
  const backToSignIn = (
    <button type="button" onClick={() => show("signin")} className="w-full text-sm text-brand-600 hover:underline">
      Back to sign in
    </button>
  );

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
                <Label>Email</Label>
                {emailInput()}
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-medium text-gray-600">Password</label>
                  <button type="button" onClick={() => show("forgot")} className="text-xs text-brand-600 hover:underline">
                    Forgot password?
                  </button>
                </div>
                <Input type="password" autoFocus={!!handedOverEmail} value={password}
                  onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
              </div>
              <PrimaryButton onClick={submit} busy={loading} busyText="Signing in...">Sign In</PrimaryButton>
            </div>
          )}

          {view === "forgot" && (
            <div className="space-y-4">
              <div>
                <Label>Email</Label>
                {emailInput({ autoFocus: true, onKeyDown: (e) => e.key === "Enter" && !notice && sendLink() })}
              </div>
              {!notice && <PrimaryButton onClick={sendLink} busy={loading} busyText="Sending...">Send reset link</PrimaryButton>}
              {backToSignIn}
            </div>
          )}

          {view === "reset" && (
            <div className="space-y-4">
              <div>
                <Label>New password</Label>
                <Input type="password" autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
                <p className="text-[11px] mt-1 text-gray-400">{PASSWORD_HINT}</p>
              </div>
              <div>
                <Label>Repeat new password</Label>
                <Input type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && savePassword()} />
              </div>
              <PrimaryButton onClick={savePassword} busy={loading} busyText="Saving...">Save password</PrimaryButton>
              {backToSignIn}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
