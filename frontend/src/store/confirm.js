import { create } from "zustand";

export const useConfirmStore = create((set) => ({
  pending: null, // { message, title, danger, resolve }
  resolve: (result) =>
    set((s) => {
      s.pending?.resolve(result);
      return { pending: null };
    }),
}));

// Drop-in async replacement for window.confirm(message) — resolves true/false.
// Pass an options object instead of a string for a custom title / danger styling.
export function confirmDialog(messageOrOptions) {
  const opts = typeof messageOrOptions === "string" ? { message: messageOrOptions } : messageOrOptions;
  return new Promise((resolve) => {
    useConfirmStore.setState({
      pending: { title: opts.title || "Please confirm", message: opts.message, danger: !!opts.danger, resolve },
    });
  });
}
