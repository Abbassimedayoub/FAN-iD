import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "./AuthContext";
import { changePassword } from "./passwordChange";
import { PasswordChangePage } from "./PasswordChangePage";
import type { AuthUser } from "./types";

vi.mock("./passwordChange", () => ({
  changePassword: vi.fn(),
}));

const admin: AuthUser = {
  id: "admin-1",
  email: "admin@example.test",
  first_name: "Admin",
  last_name: "FANID",
  role: "ADMIN",
  created_at: "2026-01-01T00:00:00Z",
};

describe("PasswordChangePage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("affiche les règles de mot de passe configurées par Django", () => {
    render(
      <AuthProvider initialUser={admin}>
        <MemoryRouter>
          <PasswordChangePage />
        </MemoryRouter>
      </AuthProvider>,
    );

    expect(screen.getByText("Contenir au moins 10 caractères.")).toBeInTheDocument();
    expect(screen.getByText("Ne pas être entièrement numérique.")).toBeInTheDocument();

    expect(
      screen.getByText(
        /Ne pas être trop similaire à votre adresse e-mail, votre nom ou vos informations personnelles/,
      ),
    ).toBeInTheDocument();

    expect(screen.getByText("Ne pas être un mot de passe couramment utilisé.")).toBeInTheDocument();
  });

  it("refuse deux nouveaux mots de passe différents avant l'appel API", async () => {
    render(
      <AuthProvider initialUser={admin}>
        <MemoryRouter>
          <PasswordChangePage />
        </MemoryRouter>
      </AuthProvider>,
    );

    fireEvent.change(screen.getByLabelText("Mot de passe actuel"), {
      target: { value: "Ancien-Mot-De-Passe-2026" },
    });

    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: { value: "Nouveau-Mot-De-Passe-2027" },
    });

    fireEvent.change(screen.getByLabelText("Confirmer le nouveau mot de passe"), {
      target: { value: "Autre-Mot-De-Passe-2027" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Changer le mot de passe" }));

    expect(
      await screen.findByText("Les deux nouveaux mots de passe ne correspondent pas."),
    ).toBeInTheDocument();

    expect(vi.mocked(changePassword)).not.toHaveBeenCalled();
  });
});
