import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useAuthStore = create(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setTokens: (accessToken, refreshToken, user) =>
        set({ accessToken, refreshToken, user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
      isAuthenticated: () => !!get().accessToken,
      role: () => get().user?.role || null,
      canEdit: () => ["admin", "rm", "ops"].includes(get().user?.role),
      isAdmin: () => get().user?.role === "admin",
      isRM: () => get().user?.role === "rm",
      isOps: () => get().user?.role === "ops",
      isScreening: () => get().user?.role === "screening",
      // BRD §15 permission flags (from /auth/login and /auth/me). Admins have every flag; the
      // fallback covers sessions stored before permissions were added to the user payload.
      can: (flag) => get().user?.role === "admin" || (get().user?.permissions || []).includes(flag),
    }),
    { name: "ezeetech-auth" }
  )
);
