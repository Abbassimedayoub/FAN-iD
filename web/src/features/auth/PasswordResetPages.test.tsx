import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ForgotPasswordPage } from "./ForgotPasswordPage";
import { PasswordResetPage } from "./PasswordResetPage";
import { confirmPasswordReset, requestPasswordReset } from "./passwordReset";

vi.mock("./passwordReset", () => ({
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ForgotPasswordPage", () => {
  it("envoie une demande générique puis propose le code de secours", async () => {
    vi.mocked(requestPasswordReset).mockResolvedValue({
      message: "Réponse générique",
      expires_in_seconds: 900,
    });

    render(
      <MemoryRouter>
        <ForgotPasswordPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Adresse e-mail"), {
      target: {
        value: " fan@example.test ",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Recevoir le lien et le code",
      }),
    );

    await waitFor(() => {
      expect(requestPasswordReset).toHaveBeenCalledWith("fan@example.test");
    });

    expect(await screen.findByText("Consultez votre boîte e-mail")).toBeInTheDocument();

    expect(
      screen.getByRole("link", {
        name: "J’ai reçu mon code à 6 chiffres",
      }),
    ).toHaveAttribute("href", "/password-reset");
  });
});

describe("PasswordResetPage", () => {
  it("utilise automatiquement le token du lien magique", async () => {
    vi.mocked(confirmPasswordReset).mockResolvedValue();

    render(
      <MemoryRouter initialEntries={["/password-reset?token=magic-token"]}>
        <Routes>
          <Route path="/password-reset" element={<PasswordResetPage />} />
          <Route path="/login" element={<p>LOGIN_DESTINATION</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: {
        value: "Grenadine-Tumultueuse-2027",
      },
    });

    fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), {
      target: {
        value: "Grenadine-Tumultueuse-2027",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Enregistrer le nouveau mot de passe",
      }),
    );

    await waitFor(() => {
      expect(confirmPasswordReset).toHaveBeenCalledWith({
        token: "magic-token",
        new_password: "Grenadine-Tumultueuse-2027",
      });
    });

    expect(await screen.findByText("LOGIN_DESTINATION")).toBeInTheDocument();
  });

  it("permet aussi la récupération manuelle avec email et code", async () => {
    vi.mocked(confirmPasswordReset).mockResolvedValue();

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/password-reset",
            state: {
              email: "fan@example.test",
            },
          },
        ]}
      >
        <Routes>
          <Route path="/password-reset" element={<PasswordResetPage />} />
          <Route path="/login" element={<p>LOGIN_DESTINATION</p>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Adresse e-mail")).toHaveValue("fan@example.test");

    fireEvent.change(screen.getByLabelText("Code à 6 chiffres"), {
      target: {
        value: "123456",
      },
    });

    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: {
        value: "Grenadine-Tumultueuse-2027",
      },
    });

    fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), {
      target: {
        value: "Grenadine-Tumultueuse-2027",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Enregistrer le nouveau mot de passe",
      }),
    );

    await waitFor(() => {
      expect(confirmPasswordReset).toHaveBeenCalledWith({
        email: "fan@example.test",
        code: "123456",
        new_password: "Grenadine-Tumultueuse-2027",
      });
    });
  });

  it("bloque localement deux mots de passe différents", async () => {
    render(
      <MemoryRouter initialEntries={["/password-reset?token=magic-token"]}>
        <PasswordResetPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Nouveau mot de passe"), {
      target: {
        value: "Grenadine-Tumultueuse-2027",
      },
    });

    fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), {
      target: {
        value: "Different-Password-2027",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Enregistrer le nouveau mot de passe",
      }),
    );

    expect(
      await screen.findByText("Les deux mots de passe ne correspondent pas."),
    ).toBeInTheDocument();

    expect(confirmPasswordReset).not.toHaveBeenCalled();
  });
});
