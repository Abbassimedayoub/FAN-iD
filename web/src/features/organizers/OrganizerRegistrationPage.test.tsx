import { fireEvent, render, screen } from "@testing-library/react";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { clearAccessToken, getAccessToken, httpClient } from "@/lib/httpClient";

import { OrganizerRegistrationPage } from "./OrganizerRegistrationPage";

const originalAdapter = httpClient.defaults.adapter;

function response(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown,
): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: status === 201 ? "Created" : "OK",
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/register/organizer"]}>
      <AuthProvider initialUser={null}>
        <Routes>
          <Route path="/register/organizer" element={<OrganizerRegistrationPage />} />
          <Route path="/organizer" element={<h1>Dossier envoyé</h1>} />
          <Route path="/login" element={<h1>Connexion</h1>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function fillAccountForm() {
  fireEvent.change(screen.getByLabelText("Prénom"), {
    target: { value: "Ines" },
  });
  fireEvent.change(screen.getByLabelText("Nom"), {
    target: { value: "Bouzid" },
  });
  fireEvent.change(screen.getByLabelText("Date de naissance"), {
    target: { value: "1996-05-04" },
  });
  fireEvent.change(screen.getByLabelText("Adresse e-mail"), {
    target: {
      value: "organizer@example.test",
    },
  });
  fireEvent.change(screen.getByLabelText("Mot de passe"), {
    target: {
      value: "Chataigne-Orageuse-2026",
    },
  });
  fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), {
    target: {
      value: "Chataigne-Orageuse-2026",
    },
  });
  fireEvent.click(screen.getByRole("checkbox"));
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  clearAccessToken();
});

describe("OrganizerRegistrationPage", () => {
  it("affiche et masque les mots de passe et valide les règles en temps réel", () => {
    renderPage();

    const passwordInput = screen.getByLabelText("Mot de passe");
    const confirmationInput = screen.getByLabelText("Confirmer le mot de passe");

    expect(passwordInput).toHaveAttribute("type", "password");
    expect(confirmationInput).toHaveAttribute("type", "password");

    fireEvent.change(passwordInput, {
      target: { value: "1234567890" },
    });

    const minimumLengthRule = screen.getByText("Contenir au moins 10 caractères.").closest("li");

    const numericRule = screen.getByText("Ne pas être entièrement numérique.").closest("li");

    expect(minimumLengthRule).toHaveClass("text-emerald-700");
    expect(numericRule).toHaveClass("text-navy/55");

    fireEvent.change(passwordInput, {
      target: { value: "MotDePasse-2026" },
    });

    expect(minimumLengthRule).toHaveClass("text-emerald-700");
    expect(numericRule).toHaveClass("text-emerald-700");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Afficher le mot de passe",
      }),
    );

    expect(passwordInput).toHaveAttribute("type", "text");
    expect(passwordInput).toHaveValue("MotDePasse-2026");

    fireEvent.change(confirmationInput, {
      target: { value: "MotDePasse-2026" },
    });

    expect(screen.getByText("✓ Les deux mots de passe correspondent.")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Afficher la confirmation du mot de passe",
      }),
    );

    expect(confirmationInput).toHaveAttribute("type", "text");
    expect(confirmationInput).toHaveValue("MotDePasse-2026");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Masquer le mot de passe",
      }),
    );

    expect(passwordInput).toHaveAttribute("type", "password");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Masquer la confirmation du mot de passe",
      }),
    );

    expect(confirmationInput).toHaveAttribute("type", "password");
  });

  it("refuse un mot de passe entièrement numérique avant tout appel réseau", async () => {
    let calls = 0;

    httpClient.defaults.adapter = async (config) => {
      calls += 1;
      return response(config, 200, {});
    };

    renderPage();
    fillAccountForm();

    fireEvent.change(screen.getByLabelText("Mot de passe"), {
      target: { value: "1234567890" },
    });

    fireEvent.change(screen.getByLabelText("Confirmer le mot de passe"), {
      target: { value: "1234567890" },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Continuer vers l’organisation",
      }),
    );

    expect(
      await screen.findByText("Le mot de passe ne peut pas être entièrement numérique."),
    ).toBeInTheDocument();

    expect(calls).toBe(0);
  });

  it("valide la première étape avant tout appel réseau", async () => {
    let calls = 0;

    httpClient.defaults.adapter = async (config) => {
      calls += 1;
      return response(config, 200, {});
    };

    renderPage();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Continuer vers l’organisation",
      }),
    );

    expect(await screen.findByText("Prénom requis.")).toBeInTheDocument();

    expect(screen.getByText("Nom requis.")).toBeInTheDocument();

    expect(screen.getByText("Adresse e-mail requise.")).toBeInTheDocument();

    expect(calls).toBe(0);
  });

  it("crée le compte, se connecte, dépose la candidature puis recharge le rôle", async () => {
    const calls: string[] = [];

    const adapter: AxiosAdapter = async (config) => {
      calls.push(`${config.method?.toUpperCase()} ${config.url}`);

      if (config.method === "post" && config.url === "/api/v1/auth/register") {
        expect(config.headers.get("Authorization")).toBeUndefined();

        expect(config.data).toBe(
          JSON.stringify({
            email: "organizer@example.test",
            password: "Chataigne-Orageuse-2026",
            first_name: "Ines",
            last_name: "Bouzid",
            date_of_birth: "1996-05-04",
            terms_accepted: true,
          }),
        );

        return response(config, 201, {
          id: "user-1",
          email: "organizer@example.test",
          first_name: "Ines",
          last_name: "Bouzid",
          role: "FAN",
          created_at: "2026-08-25T16:00:00Z",
        });
      }

      if (config.method === "post" && config.url === "/api/v1/auth/login") {
        return response(config, 200, {
          access: "organizer-access",
          user: {
            id: "user-1",
            email: "organizer@example.test",
            first_name: "Ines",
            last_name: "Bouzid",
            role: "FAN",
            created_at: "2026-08-25T16:00:00Z",
          },
          device: null,
        });
      }

      if (config.method === "post" && config.url === "/api/v1/organizers/apply") {
        expect(config.headers.get("Authorization")).toBe("Bearer organizer-access");

        expect(config.data).toBe(
          JSON.stringify({
            org_name: "Association Lumière",
            contact_email: "organizer@example.test",
            proposed_commission_rate: "0.1200",
            vat_number: "FR123456789",
          }),
        );

        return response(config, 201, {
          id: "organizer-1",
          org_name: "Association Lumière",
          validation_status: "PENDING",
          commission_rate: "0.0000",
          vat_number: "FR123456789",
          contact_email: "organizer@example.test",
          rejection_reason: null,
          validated_at: null,
          version: 1,
          created_at: "2026-08-25T16:01:00Z",
          updated_at: "2026-08-25T16:01:00Z",
        });
      }

      if (config.method === "get" && config.url === "/api/v1/auth/me") {
        return response(config, 200, {
          id: "user-1",
          email: "organizer@example.test",
          first_name: "Ines",
          last_name: "Bouzid",
          role: "ORGANIZER",
          created_at: "2026-08-25T16:00:00Z",
        });
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();
    fillAccountForm();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Continuer vers l’organisation",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Votre organisation",
      }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("E-mail de contact")).toHaveValue("organizer@example.test");

    fireEvent.change(screen.getByLabelText("Nom de l’organisation"), {
      target: {
        value: "Association Lumière",
      },
    });

    fireEvent.change(screen.getByLabelText("Proposition de commission FANID (%)"), {
      target: { value: "12" },
    });

    fireEvent.change(screen.getByLabelText(/Numéro de TVA/), {
      target: { value: "FR123456789" },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Créer mon espace organisateur",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Dossier envoyé",
      }),
    ).toBeInTheDocument();

    expect(calls).toEqual([
      "POST /api/v1/auth/register",
      "POST /api/v1/auth/login",
      "POST /api/v1/organizers/apply",
      "GET /api/v1/auth/me",
    ]);

    expect(getAccessToken()).toBe("organizer-access");
  });

  it("reprend un compte existant si le mot de passe saisi est correct", async () => {
    const calls: string[] = [];

    const adapter: AxiosAdapter = async (config) => {
      calls.push(`${config.method?.toUpperCase()} ${config.url}`);

      if (config.method === "post" && config.url === "/api/v1/auth/register") {
        const duplicate = response(config, 400, {
          error: {
            code: "EMAIL_ALREADY_EXISTS",
            message: "Un compte existe déjà avec cette adresse e-mail.",
            details: {},
          },
        });

        throw new AxiosError(
          "Request failed with status code 400",
          "ERR_BAD_REQUEST",
          config,
          undefined,
          duplicate,
        );
      }

      if (config.method === "post" && config.url === "/api/v1/auth/login") {
        expect(config.data).toBe(
          JSON.stringify({
            email: "organizer@example.test",
            password: "Chataigne-Orageuse-2026",
            client: "web",
          }),
        );

        return response(config, 200, {
          access: "existing-account-access",
          user: {
            id: "user-existing",
            email: "organizer@example.test",
            first_name: "Ines",
            last_name: "Bouzid",
            role: "FAN",
            created_at: "2026-08-25T16:00:00Z",
          },
          device: null,
        });
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();
    fillAccountForm();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Continuer vers l’organisation",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Votre organisation",
      }),
    ).toBeInTheDocument();

    expect(screen.getByLabelText("E-mail de contact")).toHaveValue("organizer@example.test");

    expect(calls).toEqual(["POST /api/v1/auth/register", "POST /api/v1/auth/login"]);

    expect(getAccessToken()).toBe("existing-account-access");
  });

  it("refuse la reprise si le mot de passe du compte existant est incorrect", async () => {
    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "post" && config.url === "/api/v1/auth/register") {
        const duplicate = response(config, 400, {
          error: {
            code: "EMAIL_ALREADY_EXISTS",
            message: "Un compte existe déjà avec cette adresse e-mail.",
            details: {},
          },
        });

        throw new AxiosError(
          "Request failed with status code 400",
          "ERR_BAD_REQUEST",
          config,
          undefined,
          duplicate,
        );
      }

      if (config.method === "post" && config.url === "/api/v1/auth/login") {
        const unauthorized = response(config, 401, {
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Identifiants invalides",
            details: {},
          },
        });

        throw new AxiosError(
          "Request failed with status code 401",
          "ERR_BAD_REQUEST",
          config,
          undefined,
          unauthorized,
        );
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();
    fillAccountForm();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Continuer vers l’organisation",
      }),
    );

    expect(
      await screen.findByText("Ce compte existe déjà, mais le mot de passe saisi est incorrect."),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("heading", {
        name: "Votre organisation",
      }),
    ).not.toBeInTheDocument();

    expect(getAccessToken()).toBeNull();
  });

  it("permet de revenir vers la connexion", () => {
    renderPage();

    expect(
      screen.getByRole("link", {
        name: "Se connecter",
      }),
    ).toHaveAttribute("href", "/login");
  });
  it("rend la proposition de commission obligatoire avant la candidature", async () => {
    let applyCalls = 0;

    httpClient.defaults.adapter = async (config) => {
      if (config.method === "post" && config.url === "/api/v1/auth/register") {
        return response(config, 201, {
          id: "user-required-commission",
          email: "organizer@example.test",
          first_name: "Ines",
          last_name: "Bouzid",
          role: "FAN",
          created_at: "2026-09-03T16:00:00Z",
        });
      }

      if (config.url === "/api/v1/organizers/apply") {
        applyCalls += 1;
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    };

    renderPage();
    fillAccountForm();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Continuer vers l’organisation",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Votre organisation",
      }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Nom de l’organisation"), {
      target: {
        value: "Association Lumière",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Créer mon espace organisateur",
      }),
    );

    expect(
      await screen.findByText("Votre proposition de commission est obligatoire."),
    ).toBeInTheDocument();

    expect(applyCalls).toBe(0);
  });
});
