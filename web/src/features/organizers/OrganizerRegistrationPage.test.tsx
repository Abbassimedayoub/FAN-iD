import { fireEvent, render, screen } from "@testing-library/react";
import {
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

  it("permet de revenir vers la connexion", () => {
    renderPage();

    expect(
      screen.getByRole("link", {
        name: "Se connecter",
      }),
    ).toHaveAttribute("href", "/login");
  });
});
