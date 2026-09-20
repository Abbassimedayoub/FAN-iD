/**
 * Zustand stores interface-only state such as filters, theme, and modals.
 * Server data lives exclusively in the TanStack Query cache and is never
 * duplicated here.
 */
import { create } from "zustand";

interface UiState {
  theme: "light" | "dark";
  activeModal: string | null;
  toggleTheme: () => void;
  openModal: (id: string) => void;
  closeModal: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  theme: "light",
  activeModal: null,
  toggleTheme: () => set((s) => ({ theme: s.theme === "light" ? "dark" : "light" })),
  openModal: (id) => set({ activeModal: id }),
  closeModal: () => set({ activeModal: null }),
}));
