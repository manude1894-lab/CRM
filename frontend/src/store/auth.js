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
    }),
    { name: "ezeetech-auth" }
  )
);
