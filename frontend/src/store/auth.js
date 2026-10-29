import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

// Each browser tab keeps its own login (Triam 29-10-2026: a person with several logins works in one tab
// per role, side by side). A refresh keeps the tab's login; closing the tab signs that tab out.
// Sessions kept by earlier versions in the shared storage are removed.
try { localStorage.removeItem("ezeetech-auth"); } catch { /* storage unavailable */ }

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
    { name: "ezeetech-auth", storage: createJSONStorage(() => sessionStorage) }
  )
);
