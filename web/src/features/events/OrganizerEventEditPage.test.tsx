import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

import { OrganizerEventEditPage } from "./OrganizerEventEditPage";

const originalAdapter = httpClient.defaults.adapter;

const organizerUser = {
  id: "user-edit-event",
  email: "organizer@example.test",
  first_name: "Dina",
  last_name: "Martin",
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

function organizerProfile(config: InternalAxiosRequestConfig): AxiosResponse {
  return response(config, {
    id: "organizer-1",
    org_name: "Organisation FANID",
    validation_status: "APPROVED",
    commission_rate: "0.0000",
    vat_number: null,
    contact_email: "organizer@example.test",
    rejection_reason: null,
    validated_at: "2026-08-25T18:00:00Z",
    version: 2,
    created_at: "2026-08-25T17:00:00Z",
    updated_at: "2026-08-25T18:00:00Z",
  });
}

function eventFixture(status = "DRAFT") {
  return {
    id: "event-edit-1",
    organizer_id: "organizer-1",
    category_id: "category-football",
    name: "Derby initial",
    description: "Description initiale",
    starts_at: "2027-09-20T18:00:00Z",
    ends_at: "2027-09-20T21:00:00Z",
    sales_starts_at: null,
    sales_ends_at: null,
    venue: "Ancien stade",
    capacity_total: 40000,
    image_url: null,
    status,
    published_at: status === "DRAFT" ? null : "2026-09-01T10:00:00Z",
    version: 3,
    created_at: "2026-08-25T20:00:00Z",
    updated_at: "2026-09-01T10:00:00Z",
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider initialUser={organizerUser}>
        <MemoryRouter initialEntries={["/organizer/events/event-edit-1/edit"]}>
          <Routes>
            <Route path="/organizer/events/:eventId/edit" element={<OrganizerEventEditPage />} />
            <Route path="/organizer/events" element={<h1>Liste des événements</h1>} />
            <Route path="/organizer/events/:eventId" element={<h1>Détail événement</h1>} />
            <Route path="/organizer" element={<h1>Dashboard</h1>} />
            <Route path="/login" element={<h1>Connexion</h1>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  return { ...result, queryClient };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("charge un brouillon, modifie ses informations et les enregistre", async () => {
  let patchedPayload: Record<string, unknown> | null = null;
  let ifMatch: unknown = null;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return organizerProfile(config);
    }
    if (config.method === "get" && config.url === "/api/v1/events/event-edit-1") {
      return response(config, eventFixture());
    }
    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, [
        { id: "category-football", name: "Football", description: "", version: 1 },
        { id: "category-concert", name: "Concert", description: "", version: 1 },
      ]);
    }
    if (config.method === "patch" && config.url === "/api/v1/events/event-edit-1") {
      patchedPayload = JSON.parse(String(config.data)) as Record<string, unknown>;
      ifMatch = config.headers?.["If-Match"];
      return response(config, {
        ...eventFixture(),
        ...patchedPayload,
        name: "Derby modifié",
        version: 4,
      });
    }
    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(await screen.findByRole("heading", { name: "Modifier l’événement" })).toBeInTheDocument();
  expect(await screen.findByRole("option", { name: "Concert" })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Nom de l’événement"), {
    target: { value: "Derby modifié" },
  });
  fireEvent.change(screen.getByLabelText("Description"), {
    target: { value: "Nouvelle description" },
  });
  fireEvent.change(screen.getByLabelText("Catégorie de l’événement"), {
    target: { value: "category-concert" },
  });
  fireEvent.change(screen.getByLabelText("Date"), {
    target: { value: "2027-10-10" },
  });
  fireEvent.change(screen.getByLabelText("Heure de début"), {
    target: { value: "19:00" },
  });
  expect(screen.getByLabelText("Heure de fin")).toHaveValue("22:00");
  fireEvent.change(screen.getByLabelText("Début des ventes (optionnel)"), {
    target: { value: "2027-10-01T09:00" },
  });
  fireEvent.change(screen.getByLabelText("Fin des ventes (optionnelle)"), {
    target: { value: "2027-10-10T18:00" },
  });
  fireEvent.change(screen.getByLabelText("Lieu"), {
    target: { value: "Nouveau stade" },
  });
  fireEvent.change(screen.getByLabelText("Capacité totale"), {
    target: { value: "45000" },
  });

  fireEvent.click(screen.getByRole("button", { name: "Enregistrer les modifications" }));

  expect(await screen.findByRole("status")).toHaveTextContent("Modifications enregistrées.");
  expect(ifMatch).toBe('"3"');
  expect(patchedPayload).toMatchObject({
    category_id: "category-concert",
    name: "Derby modifié",
    description: "Nouvelle description",
    venue: "Nouveau stade",
    capacity_total: 45000,
  });

  queryClient.clear();
});

it("bloque une sauvegarde incomplète sans appeler le PATCH", async () => {
  let patchCount = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return organizerProfile(config);
    }
    if (config.method === "get" && config.url === "/api/v1/events/event-edit-1") {
      return response(config, eventFixture());
    }
    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, [
        { id: "category-football", name: "Football", description: "", version: 1 },
      ]);
    }
    if (config.method === "patch") {
      patchCount += 1;
    }
    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();
  await screen.findByRole("heading", { name: "Modifier l’événement" });

  fireEvent.change(screen.getByLabelText("Nom de l’événement"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Enregistrer les modifications" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Le nom, la catégorie, la date et les horaires sont requis.",
  );
  expect(patchCount).toBe(0);

  queryClient.clear();
});

it("refuse les informations structurelles quand l événement n est plus un brouillon", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return organizerProfile(config);
    }
    if (config.method === "get" && config.url === "/api/v1/events/event-edit-1") {
      return response(config, eventFixture("PUBLISHED"));
    }
    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, []);
    }
    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(await screen.findByRole("heading", { name: "Événement non modifiable" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Voir l’événement" })).toHaveAttribute(
    "href",
    "/organizer/events/event-edit-1",
  );

  await waitFor(() => {
    expect(screen.queryByRole("button", { name: "Enregistrer les modifications" })).toBeNull();
  });

  queryClient.clear();
});
