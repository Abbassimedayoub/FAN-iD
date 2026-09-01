/**
 * Zustand — état d'INTERFACE uniquement (filtres, thème, modales). Règle
 * absolue (§4.3 Source B) : aucune donnée serveur dupliquée ici — les
 * données serveur vivent exclusivement dans le cache TanStack Query.
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
