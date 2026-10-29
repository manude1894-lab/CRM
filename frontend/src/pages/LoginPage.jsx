import React, { useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Input } from "../components/ui";

// Opened in a new tab from another of the person's logins: ?as=<email>&role=<role name>.
const params = new URLSearchParams(window.location.search);
const SWITCH = params.get("as") ? { email: params.get("as"), role: params.get("role") } : null;

export default function LoginPage() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const [switching, setSwitching] = useState(SWITCH);
  const [email, setEmail] = useState(SWITCH?.email || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await authApi.login(email.trim().toLowerCase(), password);
      setTokens(data.access_token, data.refresh_token, data.user, !!data.password_change_recommended);
      if (switching) window.history.replaceState(null, "", window.location.pathname);
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

          <h2 className="text-2xl font-bold text-gray-900 mb-1">{switching ? `Sign in as ${switching.role || "your other role"}` : "Sign in"}</h2>
          {switching ? (
            <p className="text-sm text-gray-500 mb-6">
              Opened from your other login, which stays open in its own tab. Enter the password for this login.{" "}
              <button type="button" className="text-brand-600 hover:underline"
                onClick={() => { setSwitching(null); setEmail(""); window.history.replaceState(null, "", window.location.pathname); }}>
                Use a different account
              </button>
            </p>
          ) : <div className="mb-5" />}

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3 mb-4">
              {error}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value.replace(/\s/g, ""))} autoCapitalize="none" autoCorrect="off"
                disabled={!!switching} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
              <Input
                type="password"
                autoFocus={!!switching}
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
        </div>
      </div>
    </div>
  );
}
