import { create } from "zustand";

let nextId = 1;

export const useToastStore = create((set) => ({
  toasts: [],
  push: (variant, message) => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, variant, message }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4500);
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

// Imperative API — usable from any handler without needing the hook.
export const toast = {
  success: (message) => useToastStore.getState().push("success", message),
  error: (message) => useToastStore.getState().push("error", message),
  info: (message) => useToastStore.getState().push("info", message),
};
