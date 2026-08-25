import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { logoutWeb } from "@/features/auth/logout";
import type { AuthUser } from "@/features/auth/types";
import { clearAccessToken, getAccessToken, setAccessToken } from "@/lib/httpClient";

import { AdminShell } from "./AdminShell";

vi.mock("@/features/auth/logout", () => ({
  logoutWeb: vi.fn(),
}));

const admin: AuthUser = {
  id: "admin-1",
  email: "admin@example.test",
  first_name: "Ada",
  last_name: "Admin",
  role: "ADMIN",
  created_at: "2026-08-20T12:00:00Z",
};

afterEach(() => {
  vi.clearAllMocks();
  clearAccessToken();
});

describe("AdminShell", () => {
  it("affiche la déconnexion dans l'espace administrateur", () => {
    const queryClient = new QueryClient();

    render(
      <MemoryRouter initialEntries={["/admin/organizers"]}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider initialUser={admin}>
            <AdminShell>
              <h1>Organisateurs</h1>
            </AdminShell>
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();

    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("déconnecte côté serveur, vide le cache privé et revient au login", async () => {
    vi.mocked(logoutWeb).mockResolvedValue(undefined);

    const queryClient = new QueryClient();
    queryClient.setQueryData(["private-admin-data"], { secret: true });

    setAccessToken("admin-access-token");

    render(
      <MemoryRouter initialEntries={["/admin/organizers"]}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider initialUser={admin}>
            <Routes>
              <Route
                path="/admin/organizers"
                element={
                  <AdminShell>
                    <h1>Organisateurs</h1>
                  </AdminShell>
                }
              />
              <Route path="/login" element={<h1>Connexion</h1>} />
            </Routes>
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Se déconnecter" }));

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();

    expect(logoutWeb).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();

    await waitFor(() => {
      expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    });
  });
});
