import React, { useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Input } from "../components/ui";

const DEMO_ACCOUNTS = [
  { name: "Admin User", email: "admin@ezeetechgroup.com", password: "admin123", role: "Admin" },
];

export default function LoginPage() {
  const setTokens = useAuthStore((s) => s.setTokens);
  const [email, setEmail] = useState("admin@ezeetechgroup.com");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await authApi.login(email, password);
      setTokens(data.access_token, data.refresh_token, data.user);
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
          style={{ background: "#2B6D9A" }}
        />
        <div className="relative">
          <div className="inline-flex items-center justify-center bg-white rounded-2xl p-3 shadow-xl">
            <img src="/triam-logo.png" alt="TRIAM" className="h-10 w-auto" />
          </div>
        </div>
        <div className="relative">
          <h1 className="text-3xl font-bold text-white leading-tight mb-3">
            Entity Servicing &amp;<br />Compliance Platform
          </h1>
          <p className="text-blue-200 text-sm max-w-sm">
            Formation, CDD/KYC, AML risk assessment and compliance tracking for BVI and offshore entities — end to end, in one place.
          </p>
        </div>
        <div className="relative flex items-center gap-6 text-blue-200 text-xs">
          <span>© {new Date().getFullYear()} Triam Management Services</span>
        </div>
      </div>

      {/* Sign-in panel */}
      <div className="flex-1 flex items-center justify-center p-6 bg-gray-50">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex flex-col items-center mb-8">
            <div className="inline-flex items-center justify-center bg-white rounded-2xl p-3 shadow-md border border-gray-100 mb-3">
              <img src="/triam-logo.png" alt="TRIAM" className="h-9 w-auto" />
            </div>
            <p className="text-gray-500 text-sm">Entity Servicing &amp; Compliance Platform</p>
          </div>

          <h2 className="text-2xl font-bold text-gray-900 mb-1">Welcome back</h2>
          <p className="text-sm text-gray-500 mb-6">Sign in to your account to continue</p>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3 mb-4">
              {error}
            </div>
          )}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
            </div>
            <button
              onClick={submit}
              disabled={loading}
              className="w-full text-white font-semibold py-2.5 rounded-lg transition-opacity hover:opacity-90 disabled:opacity-60 shadow-sm"
              style={{ background: "#2B6D9A" }}
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </div>
          <div className="mt-6 pt-5 border-t border-gray-200">
            <p className="text-xs text-gray-500 font-medium mb-2">Demo accounts:</p>
            {DEMO_ACCOUNTS.map((u) => (
              <button
                key={u.email}
                onClick={() => {
                  setEmail(u.email);
                  setPassword(u.password);
                }}
                className="w-full text-left text-xs text-gray-600 hover:text-blue-600 py-1.5 px-2 rounded hover:bg-white border border-transparent hover:border-gray-200 transition-colors mb-0.5"
              >
                <span className="font-medium">{u.name}</span>{" "}
                <span className="text-gray-400">({u.role})</span> — {u.email}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
