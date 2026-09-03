import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

import { OrganizerEventCreatePage } from "./OrganizerEventCreatePage";

const originalAdapter = httpClient.defaults.adapter;

const organizerUser = {
  id: "user-organizer-event",
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
        <MemoryRouter initialEntries={["/organizer/events/new"]}>
          <Routes>
            <Route path="/organizer/events/new" element={<OrganizerEventCreatePage />} />
            <Route path="/organizer/events" element={<h1>Liste des événements</h1>} />
            <Route path="/organizer" element={<h1>Dashboard</h1>} />
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

it("affiche l écran ORG-07 pour un organisateur approuvé", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
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

    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, [
        {
          id: "category-football",
          name: "Football",
          description: "",
          version: 1,
        },
      ]);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Créer un événement",
    }),
  ).toBeInTheDocument();

  expect(screen.getByText("Catégories & quotas")).toBeInTheDocument();

  expect(
    await screen.findByRole("option", {
      name: "Football",
    }),
  ).toBeInTheDocument();

  expect(
    screen.getByRole("navigation", {
      name: "Navigation organisateur principale",
    }),
  ).toBeInTheDocument();

  queryClient.clear();
});

it("crée réellement un brouillon avec les informations saisies", async () => {
  let createdPayload: Record<string, unknown> | null = null;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
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

    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, [
        {
          id: "category-football",
          name: "Football",
          description: "",
          version: 1,
        },
      ]);
    }

    if (config.method === "post" && config.url === "/api/v1/events") {
      createdPayload = JSON.parse(String(config.data)) as Record<string, unknown>;

      return response(
        config,
        {
          id: "event-1",
          organizer_id: "organizer-1",
          category_id: "category-football",
          name: "Derby FANID",
          description: "Grand match",
          starts_at: "2026-09-20T18:00:00Z",
          ends_at: "2026-09-20T21:00:00Z",
          venue: "Stade FANID",
          capacity_total: 45000,
          image_url: null,
          status: "DRAFT",
          published_at: null,
          version: 1,
          created_at: "2026-08-25T20:00:00Z",
          updated_at: "2026-08-25T20:00:00Z",
        },
        201,
      );
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  await screen.findByRole("option", {
    name: "Football",
  });

  fireEvent.change(screen.getByLabelText("Nom de l’événement"), {
    target: {
      value: "Derby FANID",
    },
  });

  fireEvent.change(screen.getByLabelText("Description"), {
    target: {
      value: "Grand match",
    },
  });

  fireEvent.change(screen.getByLabelText("Catégorie de l’événement"), {
    target: {
      value: "category-football",
    },
  });

  fireEvent.change(screen.getByLabelText("Date"), {
    target: {
      value: "2026-09-20",
    },
  });

  fireEvent.change(screen.getByLabelText("Heure de début"), {
    target: {
      value: "18:00",
    },
  });

  expect(screen.getByLabelText("Heure de fin")).toHaveValue("21:00");

  fireEvent.change(screen.getByLabelText("Heure de fin"), {
    target: {
      value: "21:00",
    },
  });

  fireEvent.change(screen.getByLabelText("Capacité totale"), {
    target: {
      value: "45000",
    },
  });

  fireEvent.change(screen.getByLabelText("Lieu"), {
    target: {
      value: "Stade FANID",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Enregistrer le brouillon",
    }),
  );

  expect(await screen.findByText("Brouillon enregistré.")).toBeInTheDocument();

  expect(createdPayload).not.toBeNull();

  expect(createdPayload?.["category_id"]).toBe("category-football");

  expect(createdPayload?.["capacity_total"]).toBe(45000);

  expect(createdPayload?.["venue"]).toBe("Stade FANID");

  queryClient.clear();
});

it("bloque la gestion événementielle tant que l organisateur n est pas approuvé", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, {
        id: "organizer-1",
        org_name: "Organisation FANID",
        validation_status: "PENDING",
        commission_rate: "0.0000",
        vat_number: null,
        contact_email: "organizer@example.test",
        rejection_reason: null,
        validated_at: null,
        version: 1,
        created_at: "2026-08-25T17:00:00Z",
        updated_at: "2026-08-25T17:00:00Z",
      });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", {
      name: "Gestion des événements indisponible",
    }),
  ).toBeInTheDocument();

  queryClient.clear();
});

it("continue vers les catégories puis crée une catégorie de billets", async () => {
  const ticketCategories: Array<{
    id: string;
    event_id: string;
    name: string;
    quota: number;
    sold_count: number;
    available_count: number;
    unit_price_cents: number;
    version: number;
    created_at: string;
    updated_at: string;
  }> = [];

  let createdTicketPayload: Record<string, unknown> | null = null;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
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

    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, [
        {
          id: "category-football",
          name: "Football",
          description: "",
          version: 1,
        },
      ]);
    }

    if (config.method === "post" && config.url === "/api/v1/events") {
      return response(
        config,
        {
          id: "event-step2",
          organizer_id: "organizer-1",
          category_id: "category-football",
          name: "Derby FANID",
          description: "Grand match",
          starts_at: "2026-09-20T18:00:00Z",
          ends_at: "2026-09-20T21:00:00Z",
          venue: "Stade FANID",
          capacity_total: 45000,
          image_url: null,
          status: "DRAFT",
          published_at: null,
          version: 1,
          created_at: "2026-08-25T20:00:00Z",
          updated_at: "2026-08-25T20:00:00Z",
        },
        201,
      );
    }

    if (config.method === "get" && config.url === "/api/v1/events/event-step2/ticket-categories") {
      return response(config, ticketCategories);
    }

    if (config.method === "post" && config.url === "/api/v1/events/event-step2/ticket-categories") {
      createdTicketPayload = JSON.parse(String(config.data)) as Record<string, unknown>;

      const created = {
        id: "ticket-category-1",
        event_id: "event-step2",
        name: "Tribune Honneur",
        quota: 1000,
        sold_count: 0,
        available_count: 1000,
        unit_price_cents: 2550,
        version: 1,
        created_at: "2026-08-25T20:01:00Z",
        updated_at: "2026-08-25T20:01:00Z",
      };

      ticketCategories.push(created);

      return response(config, created, 201);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  await screen.findByRole("option", {
    name: "Football",
  });

  fireEvent.change(screen.getByLabelText("Nom de l’événement"), {
    target: {
      value: "Derby FANID",
    },
  });

  fireEvent.change(screen.getByLabelText("Description"), {
    target: {
      value: "Grand match",
    },
  });

  fireEvent.change(screen.getByLabelText("Catégorie de l’événement"), {
    target: {
      value: "category-football",
    },
  });

  fireEvent.change(screen.getByLabelText("Date"), {
    target: {
      value: "2026-09-20",
    },
  });

  fireEvent.change(screen.getByLabelText("Heure de début"), {
    target: {
      value: "18:00",
    },
  });

  fireEvent.change(screen.getByLabelText("Heure de fin"), {
    target: {
      value: "21:00",
    },
  });

  fireEvent.change(screen.getByLabelText("Capacité totale"), {
    target: {
      value: "45000",
    },
  });

  fireEvent.change(screen.getByLabelText("Lieu"), {
    target: {
      value: "Stade FANID",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Continuer vers les catégories",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Catégories & quotas",
    }),
  ).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Nom de la catégorie de billets"), {
    target: {
      value: "Tribune Honneur",
    },
  });

  fireEvent.change(screen.getByLabelText("Quota"), {
    target: {
      value: "1000",
    },
  });

  fireEvent.change(screen.getByLabelText("Prix unitaire (€)"), {
    target: {
      value: "25,50",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Ajouter la catégorie",
    }),
  );

  expect(await screen.findByText("Tribune Honneur")).toBeInTheDocument();

  expect(createdTicketPayload).not.toBeNull();

  expect(createdTicketPayload?.["quota"]).toBe(1000);

  expect(createdTicketPayload?.["unit_price_cents"]).toBe(2550);

  expect(screen.getByText("44000")).toBeInTheDocument();

  queryClient.clear();
});

it("publie réellement un événement prêt", async () => {
  const ticketCategories = [
    {
      id: "ticket-publish-1",
      event_id: "event-publish",
      name: "Tribune Honneur",
      quota: 1000,
      sold_count: 0,
      available_count: 1000,
      unit_price_cents: 2500,
      version: 1,
      created_at: "2026-08-25T20:01:00Z",
      updated_at: "2026-08-25T20:01:00Z",
    },
  ];

  let publishCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
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

    if (config.method === "get" && config.url === "/api/v1/categories") {
      return response(config, [
        {
          id: "category-football",
          name: "Football",
          description: "",
          version: 1,
        },
      ]);
    }

    if (config.method === "post" && config.url === "/api/v1/events") {
      return response(
        config,
        {
          id: "event-publish",
          organizer_id: "organizer-1",
          category_id: "category-football",
          name: "Derby FANID",
          description: "Grand match",
          starts_at: "2026-09-20T18:00:00Z",
          ends_at: "2026-09-20T21:00:00Z",
          venue: "Stade FANID",
          capacity_total: 45000,
          image_url: null,
          status: "DRAFT",
          published_at: null,
          version: 1,
          created_at: "2026-08-25T20:00:00Z",
          updated_at: "2026-08-25T20:00:00Z",
        },
        201,
      );
    }

    if (
      config.method === "get" &&
      config.url === "/api/v1/events/event-publish/ticket-categories"
    ) {
      return response(config, ticketCategories);
    }

    if (config.method === "post" && config.url === "/api/v1/events/event-publish/publish") {
      publishCalls += 1;

      expect(config.headers.get("If-Match")).toBe('"1"');

      return response(config, {
        id: "event-publish",
        organizer_id: "organizer-1",
        category_id: "category-football",
        name: "Derby FANID",
        description: "Grand match",
        starts_at: "2026-09-20T18:00:00Z",
        ends_at: "2026-09-20T21:00:00Z",
        venue: "Stade FANID",
        capacity_total: 45000,
        image_url: null,
        status: "PUBLISHED",
        published_at: "2026-08-25T21:00:00Z",
        version: 2,
        created_at: "2026-08-25T20:00:00Z",
        updated_at: "2026-08-25T21:00:00Z",
      });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  await screen.findByRole("option", {
    name: "Football",
  });

  fireEvent.change(screen.getByLabelText("Nom de l’événement"), {
    target: {
      value: "Derby FANID",
    },
  });

  fireEvent.change(screen.getByLabelText("Description"), {
    target: {
      value: "Grand match",
    },
  });

  fireEvent.change(screen.getByLabelText("Catégorie de l’événement"), {
    target: {
      value: "category-football",
    },
  });

  fireEvent.change(screen.getByLabelText("Date"), {
    target: {
      value: "2026-09-20",
    },
  });

  fireEvent.change(screen.getByLabelText("Heure de début"), {
    target: {
      value: "18:00",
    },
  });

  fireEvent.change(screen.getByLabelText("Heure de fin"), {
    target: {
      value: "21:00",
    },
  });

  fireEvent.change(screen.getByLabelText("Capacité totale"), {
    target: {
      value: "45000",
    },
  });

  fireEvent.change(screen.getByLabelText("Lieu"), {
    target: {
      value: "Stade FANID",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Continuer vers les catégories",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Catégories & quotas",
    }),
  ).toBeInTheDocument();

  expect(await screen.findByText("Tribune Honneur")).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Continuer vers la publication",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Vérifier et publier",
    }),
  ).toBeInTheDocument();

  expect(await screen.findByText("Prêt à publier")).toBeInTheDocument();

  const publishButton = screen.getByRole("button", {
    name: "Publier l’événement",
  });

  expect(publishButton).toBeEnabled();

  fireEvent.click(publishButton);

  expect(
    await screen.findByRole("heading", {
      name: "Liste des événements",
    }),
  ).toBeInTheDocument();

  expect(publishCalls).toBe(1);

  queryClient.clear();
});
