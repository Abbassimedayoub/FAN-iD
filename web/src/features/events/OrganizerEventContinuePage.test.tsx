import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

import { OrganizerEventContinuePage } from "./OrganizerEventContinuePage";

const originalAdapter = httpClient.defaults.adapter;

const organizerUser = {
  id: "user-organizer-continue",
  email: "continue@example.test",
  first_name: "Dina",
  last_name: "Martin",
  role: "ORGANIZER" as const,
  created_at: "2026-08-30T10:00:00Z",
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

function draftEvent() {
  return {
    id: "event-resume",
    organizer_id: "organizer-1",
    category_id: "category-football",
    name: "Derby à reprendre",
    description: "Brouillon sauvegardé",
    starts_at: "2026-09-20T18:00:00Z",
    ends_at: "2026-09-20T21:00:00Z",
    venue: "Stade FANID",
    capacity_total: 100,
    image_url: null,
    status: "DRAFT",
    published_at: null,
    lifecycle_reason: "",
    lifecycle_changed_at: null,
    version: 4,
    created_at: "2026-08-30T10:00:00Z",
    updated_at: "2026-08-30T10:30:00Z",
  };
}

const ticketCategories = [
  {
    id: "ticket-resume-1",
    event_id: "event-resume",
    name: "Tribune",
    quota: 100,
    sold_count: 0,
    available_count: 100,
    unit_price_cents: 2500,
    version: 1,
    created_at: "2026-08-30T10:05:00Z",
    updated_at: "2026-08-30T10:05:00Z",
  },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider initialUser={organizerUser}>
        <MemoryRouter initialEntries={["/organizer/events/event-resume/continue"]}>
          <Routes>
            <Route
              path="/organizer/events/:eventId/continue"
              element={<OrganizerEventContinuePage />}
            />

            <Route path="/organizer/events/:eventId" element={<h1>Détail événement</h1>} />

            <Route path="/organizer/events/:eventId/edit" element={<h1>Modifier événement</h1>} />
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

it("permet de sauvegarder le brouillon depuis les catégories et quitter", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/events/event-resume") {
      return response(config, draftEvent());
    }

    if (config.method === "get" && config.url === "/api/v1/events/event-resume/ticket-categories") {
      return response(config, ticketCategories);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Catégories & quotas",
    }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Enregistrer le brouillon et quitter",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Détail événement",
    }),
  ).toBeInTheDocument();

  queryClient.clear();
});

it("reprend un brouillon jusqu à la publication", async () => {
  let publishCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/events/event-resume") {
      return response(config, draftEvent());
    }

    if (config.method === "get" && config.url === "/api/v1/events/event-resume/ticket-categories") {
      return response(config, ticketCategories);
    }

    if (config.method === "post" && config.url === "/api/v1/events/event-resume/publish") {
      publishCalls += 1;

      expect(config.headers.get("If-Match")).toBe('"4"');

      return response(config, {
        ...draftEvent(),
        status: "PUBLISHED",
        published_at: "2026-08-30T11:00:00Z",
        version: 5,
      });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Catégories & quotas",
    }),
  ).toBeInTheDocument();

  expect(await screen.findByText("Tribune")).toBeInTheDocument();

  const continueButton = screen.getByRole("button", {
    name: "Continuer vers la publication",
  });

  expect(continueButton).toBeEnabled();

  fireEvent.click(continueButton);

  expect(
    await screen.findByRole("heading", {
      name: "Vérifier et publier",
    }),
  ).toBeInTheDocument();

  expect(await screen.findByText("Prêt à publier")).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Publier l’événement",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Événement publié",
    }),
  ).toBeInTheDocument();

  expect(publishCalls).toBe(1);

  queryClient.clear();
});
