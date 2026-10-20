import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useAuthStore = create(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      passwordChangeRecommended: false, // signed in with a default password
      setTokens: (accessToken, refreshToken, user, passwordChangeRecommended = false) =>
        set({ accessToken, refreshToken, user, passwordChangeRecommended }),
      clearPasswordWarning: () => set({ passwordChangeRecommended: false }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null, passwordChangeRecommended: false }),
      isAuthenticated: () => !!get().accessToken,
      role: () => get().user?.role || null,
      isAdmin: () => get().user?.role === "admin",
      // BRD §13 permission flags (from /auth/login and /auth/me). Admins have every flag; the
      // fallback covers sessions stored before permissions were added to the user payload.
      can: (flag) => get().user?.role === "admin" || (get().user?.permissions || []).includes(flag),
    }),
    { name: "ezeetech-auth" }
  )
);
