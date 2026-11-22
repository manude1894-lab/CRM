import { authApi } from "../api/endpoints";
import { useAuthStore } from "../store/auth";

// Sign out: end the session on the server (so a copied token stops working at once), then clear this tab.
// The browser is cleared even when the server can't be reached.
export async function signOut() {
  try { await authApi.logout(); } catch { /* offline or already expired: clear the tab anyway */ }
  useAuthStore.getState().logout();
}
