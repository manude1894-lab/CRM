import React, { useState } from "react";
import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";
import { Input } from "../components/ui";

const DEMO_ACCOUNTS = [
  { name: "Admin User", email: "admin@ezeetechgroup.com", password: "admin123", role: "Admin" },
  { name: "Venkata Ram", email: "venkata@ezeetechgroup.com", password: "triam123", role: "RM" },
  { name: "Abdul Salman", email: "abdul@ezeetechgroup.com", password: "triam123", role: "RM" },
  { name: "Manohar Ganna", email: "manohar@ezeetechgroup.com", password: "triam123", role: "RM" },
  { name: "Nishit Poddar", email: "nishit@ezeetechgroup.com", password: "triam123", role: "Screening" },
  { name: "Priya Kumar", email: "priya@ezeetechgroup.com", password: "triam123", role: "Ops" },
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
    <div
      className="min-h-screen flex items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #0f1c2e 0%, #1a3a5c 50%, #0d2b45 100%)" }}
    >
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div
            className="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4"
            style={{ background: "#2B6D9A" }}
          >
            <span className="text-white text-2xl font-bold">E</span>
          </div>
          <h1 className="text-3xl font-bold text-white">EZEETECH GROUP</h1>
          <p className="text-blue-300 mt-1 text-sm">DIFC Client Onboarding & Compliance Tracker</p>
        </div>
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Sign in to your account</h2>
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
              className="w-full text-white font-semibold py-2.5 rounded-lg transition-opacity hover:opacity-90 disabled:opacity-60"
              style={{ background: "#2B6D9A" }}
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </div>
          <div className="mt-5 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-500 font-medium mb-2">Demo accounts:</p>
            {DEMO_ACCOUNTS.map((u) => (
              <button
                key={u.email}
                onClick={() => {
                  setEmail(u.email);
                  setPassword(u.password);
                }}
                className="w-full text-left text-xs text-gray-600 hover:text-blue-600 py-1 px-2 rounded hover:bg-blue-50 transition-colors mb-0.5"
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
