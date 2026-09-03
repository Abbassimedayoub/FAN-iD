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

function organizer(validationStatus: "PENDING" | "APPROVED" | "SUSPENDED") {
  return {
    id: "organizer-1",
    org_name: "Association Lumière",
    validation_status: validationStatus,
    commission_rate: "0.0000",
    vat_number: null,
    contact_email: "contact@example.test",
    rejection_reason: null,
    validated_at: validationStatus === "PENDING" ? null : "2026-08-25T17:00:00Z",
    version: validationStatus === "PENDING" ? 1 : validationStatus === "APPROVED" ? 2 : 3,
    created_at: "2026-08-25T16:00:00Z",
    updated_at: "2026-08-25T16:00:00Z",
  };
}

function negotiating(validationStatus: "PENDING" | "APPROVED") {
  return {
    organizer_id: "organizer-1",
    validation_status: validationStatus,
    commission_status: "NEGOTIATING",
    agreed_rate: null,
    agreed_at: null,
    version: validationStatus === "PENDING" ? 1 : 2,
    proposals: [
      {
        id: "proposal-1",
        sequence: 1,
        proposer_role: "ORGANIZER",
        proposed_by_id: "user-organizer-1",
        rate: "0.1200",
        created_at: "2026-08-25T16:01:00Z",
        accepted_at: null,
        accepted_by_id: null,
      },
    ],
  };
}

function agreed() {
  return {
    organizer_id: "organizer-1",
    validation_status: "APPROVED",
    commission_status: "COMMISSION_AGREED",
    agreed_rate: "0.1000",
    agreed_at: "2026-08-25T18:00:00Z",
    version: 3,
    proposals: [
      {
        id: "proposal-1",
        sequence: 1,
        proposer_role: "ORGANIZER",
        proposed_by_id: "user-organizer-1",
        rate: "0.1000",
        created_at: "2026-08-25T16:01:00Z",
        accepted_at: "2026-08-25T18:00:00Z",
        accepted_by_id: "admin-1",
      },
    ],
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

    if (config.method === "get" && config.url === "/api/v1/organizers/me/commission-negotiation") {
      return response(config, negotiating("PENDING"));
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
      name: "Événements verrouillés",
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

    if (config.method === "get" && config.url === "/api/v1/organizers/me/commission-negotiation") {
      return response(config, agreed());
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
    await screen.findByRole("link", {
      name: "Créer un événement",
    }),
  ).toHaveAttribute("href", "/organizer/events/new");

  expect(
    screen.getByRole("link", {
      name: "Événements",
    }),
  ).toHaveAttribute("href", "/organizer/events");

  expect(requestedUrls).toEqual([
    "/api/v1/organizers/me",
    "/api/v1/organizers/me/commission-negotiation",
  ]);

  queryClient.clear();
});

it("garde les événements verrouillés pour un compte APPROVED tant que la commission négocie", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, organizer("APPROVED"));
    }

    if (config.method === "get" && config.url === "/api/v1/organizers/me/commission-negotiation") {
      return response(config, negotiating("APPROVED"));
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
      name: "Événements verrouillés",
    }),
  ).toBeDisabled();

  expect(
    screen.queryByRole("link", {
      name: "Créer un événement",
    }),
  ).not.toBeInTheDocument();

  expect(
    screen.getByText(
      "Votre compte est approuvé, mais un accord de commission avec FANID est requis avant de créer ou gérer des événements.",
    ),
  ).toBeInTheDocument();

  queryClient.clear();
});

it("permet à un organisateur suspendu de demander la réouverture sans se réactiver lui-même", async () => {
  let requestCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, organizer("SUSPENDED"));
    }

    if (config.method === "get" && config.url === "/api/v1/organizers/me/reactivation-request") {
      return response(config, {
        request: null,
      });
    }

    if (config.method === "post" && config.url === "/api/v1/organizers/me/reactivation-request") {
      requestCalls += 1;

      return response(
        config,
        {
          id: "reactivation-request-1",
          organizer_id: "organizer-1",
          requested_by_id: "user-organizer-1",
          organizer_version: 3,
          status: "PENDING",
          reviewed_by_id: null,
          reviewed_at: null,
          rejection_reason: null,
          created_at: "2026-08-30T16:00:00Z",
          updated_at: "2026-08-30T16:00:00Z",
        },
        201,
      );
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Compte organisateur suspendu",
    }),
  ).toBeInTheDocument();

  expect(
    await screen.findByRole("button", {
      name: "Demander la réouverture",
    }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Demander la réouverture",
    }),
  );

  expect(
    await screen.findByText("Demande de réouverture en attente de validation administrateur."),
  ).toBeInTheDocument();

  expect(
    screen.getByRole("heading", {
      name: "Compte organisateur suspendu",
    }),
  ).toBeInTheDocument();

  expect(
    screen.queryByRole("button", {
      name: "Réouvrir mon compte",
    }),
  ).not.toBeInTheDocument();

  expect(
    screen.queryByRole("link", {
      name: "Créer un événement",
    }),
  ).not.toBeInTheDocument();

  expect(requestCalls).toBe(1);

  queryClient.clear();
});

it("déconnecte réellement l’organisateur puis revient à la connexion", async () => {
  let logoutCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, organizer("APPROVED"));
    }

    if (config.method === "get" && config.url === "/api/v1/organizers/me/commission-negotiation") {
      return response(config, agreed());
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
