import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

import { OrganizerEventsPage } from "./OrganizerEventsPage";

const originalAdapter = httpClient.defaults.adapter;

function response(config: InternalAxiosRequestConfig, data: unknown): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status: 200,
    statusText: "OK",
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("liste les événements et propose la modification des brouillons", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (config.url === "/api/v1/organizers/me") {
      return response(config, {
        id: "org-1",
        org_name: "FANID Org",
        validation_status: "APPROVED",
        commission_rate: "0.0000",
        vat_number: null,
        contact_email: "org@example.test",
        rejection_reason: null,
        validated_at: "2026-08-25T18:00:00Z",
        version: 1,
        created_at: "2026-08-25T17:00:00Z",
        updated_at: "2026-08-25T18:00:00Z",
      });
    }

    if (config.url === "/api/v1/events") {
      return response(config, {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: "event-1",
            organizer_id: "org-1",
            category_id: "football",
            name: "Derby FANID",
            description: "Grand match",
            starts_at: "2026-09-20T18:00:00Z",
            ends_at: "2026-09-20T21:00:00Z",
            venue: "Stade FANID",
            capacity_total: 45000,
            image_url: null,
            status: "DRAFT",
            published_at: null,
            version: 2,
            created_at: "2026-08-25T20:00:00Z",
            updated_at: "2026-08-25T20:00:00Z",
          },
        ],
      });
    }

    throw new Error(`Unexpected ${config.method} ${config.url}`);
  };

  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={client}>
      <AuthProvider
        initialUser={{
          id: "user-1",
          email: "org@example.test",
          first_name: "Dina",
          last_name: "Martin",
          role: "ORGANIZER",
          created_at: "2026-08-25T17:00:00Z",
        }}
      >
        <MemoryRouter>
          <OrganizerEventsPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Derby FANID")).toBeInTheDocument();

  expect(
    screen.getByRole("link", {
      name: "Modifier",
    }),
  ).toHaveAttribute("href", "/organizer/events/event-1/edit");

  expect(
    screen.getByRole("button", {
      name: "Supprimer définitivement",
    }),
  ).toBeInTheDocument();

  expect(
    screen.getByRole("link", {
      name: "Voir",
    }),
  ).toHaveAttribute("href", "/organizer/events/event-1");

  client.clear();
});
