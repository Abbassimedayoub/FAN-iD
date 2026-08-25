import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { getAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import { OrganizerHomePage } from "./OrganizerHomePage";

const originalAdapter = httpClient.defaults.adapter;

const organizerUser = {
  id: "user-organizer-1",
  email: "organizer@example.test",
  first_name: "Ines",
  last_name: "Bouzid",
  role: "ORGANIZER" as const,
  created_at: "2026-08-25T15:00:00Z",
};

function response(config: InternalAxiosRequestConfig, data: unknown, status = 200): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: "OK",
  };
}

function organizer(validationStatus: "PENDING" | "APPROVED") {
  return {
    id: "organizer-1",
    org_name: "Association Lumière",
    validation_status: validationStatus,
    commission_rate: "0.0000",
    vat_number: null,
    contact_email: "contact@example.test",
    rejection_reason: null,
    validated_at: validationStatus === "APPROVED" ? "2026-08-25T17:00:00Z" : null,
    version: validationStatus === "APPROVED" ? 2 : 1,
    created_at: "2026-08-25T16:00:00Z",
    updated_at: "2026-08-25T16:00:00Z",
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider initialUser={organizerUser}>
        <MemoryRouter initialEntries={["/organizer"]}>
          <Routes>
            <Route path="/organizer" element={<OrganizerHomePage />} />
            <Route path="/login" element={<h1>Connexion</h1>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  return {
    ...result,
    queryClient,
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("affiche le statut PENDING et les outils de compte", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, organizer("PENDING"));
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Demande en cours d’examen",
    }),
  ).toBeInTheDocument();

  expect(screen.getByText("Association Lumière")).toBeInTheDocument();

  expect(
    screen.getByRole("navigation", {
      name: "Navigation organisateur",
    }),
  ).toBeInTheDocument();

  const passwordLinks = screen.getAllByRole("link", {
    name: "Changer le mot de passe",
  });

  expect(passwordLinks.length).toBeGreaterThan(0);
  expect(passwordLinks[0]).toHaveAttribute("href", "/organizer/security");

  expect(
    screen.getByRole("link", {
      name: "Sessions",
    }),
  ).toHaveAttribute("href", "/sessions");

  expect(
    screen.getByRole("button", {
      name: "Événements bientôt disponibles",
    }),
  ).toBeDisabled();

  queryClient.clear();
});

it("affiche le tableau de bord APPROVED sans inventer un endpoint événementiel", async () => {
  const requestedUrls: string[] = [];

  httpClient.defaults.adapter = async (config) => {
    requestedUrls.push(config.url ?? "");

    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, organizer("APPROVED"));
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Compte organisateur validé",
    }),
  ).toBeInTheDocument();

  expect(
    screen.getByRole("button", {
      name: "Créer un événement · bientôt",
    }),
  ).toBeDisabled();

  expect(requestedUrls).toEqual(["/api/v1/organizers/me"]);

  queryClient.clear();
});

it("déconnecte réellement l’organisateur puis revient à la connexion", async () => {
  let logoutCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, organizer("APPROVED"));
    }

    if (config.method === "post" && config.url === "/api/v1/auth/logout") {
      logoutCalls += 1;
      return response(config, undefined, 204);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  setAccessToken("organizer-access-token");

  const { queryClient } = renderPage();

  await screen.findByRole("heading", {
    name: "Compte organisateur validé",
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Se déconnecter",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Connexion",
    }),
  ).toBeInTheDocument();

  expect(logoutCalls).toBe(1);
  expect(getAccessToken()).toBeNull();

  await waitFor(() => {
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
  });
});
