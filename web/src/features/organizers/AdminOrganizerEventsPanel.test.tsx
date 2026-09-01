import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { AdminOrganizerEventsPanel } from "./AdminOrganizerEventsPanel";

const originalAdapter = httpClient.defaults.adapter;

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

function response(config: InternalAxiosRequestConfig): AxiosResponse {
  return {
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: "event-1",
          organizer_id: "org-1",
          category_id: "cat-1",
          name: "Finale FANID",
          description: "",
          starts_at: "2026-09-20T18:00:00Z",
          ends_at: "2026-09-20T20:00:00Z",
          postponed_from_starts_at: "2026-09-10T18:00:00Z",
          postponed_from_ends_at: "2026-09-10T20:00:00Z",
          postponed_to_starts_at: "2026-09-20T18:00:00Z",
          postponed_to_ends_at: "2026-09-20T20:00:00Z",
          venue: "Stade FANID",
          capacity_total: 75,
          image_url: null,
          status: "POSTPONED",
          published_at: "2026-08-01T10:00:00Z",
          lifecycle_reason: "Nouvelle programmation",
          lifecycle_changed_at: "2026-09-01T10:00:00Z",
          version: 3,
          created_at: "2026-08-01T08:00:00Z",
          updated_at: "2026-09-01T10:00:00Z",
          ticket_categories: [
            {
              id: "ticket-vip",
              event_id: "event-1",
              name: "VIP",
              quota: 50,
              sold_count: 48,
              available_count: 2,
              unit_price_cents: 2500,
              version: 1,
              created_at: "2026-08-01T08:00:00Z",
              updated_at: "2026-08-01T08:00:00Z",
            },
            {
              id: "ticket-virage",
              event_id: "event-1",
              name: "Virage",
              quota: 25,
              sold_count: 22,
              available_count: 3,
              unit_price_cents: 1500,
              version: 1,
              created_at: "2026-08-01T08:00:00Z",
              updated_at: "2026-08-01T08:00:00Z",
            },
          ],
        },
      ],
    },
    status: 200,
    statusText: "OK",
    headers: {},
    config,
  };
}

it("charge les événements et affiche les ventes uniquement dans les détails", async () => {
  const calls: string[] = [];

  const adapter: AxiosAdapter = async (config) => {
    calls.push(`${String(config.method).toUpperCase()} ${config.url}`);

    return response(config);
  };

  httpClient.defaults.adapter = adapter;

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <AdminOrganizerEventsPanel organizerId="org-1" />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Finale FANID")).toBeInTheDocument();

  expect(screen.queryByText("48/50")).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Voir les détails",
    }),
  );

  expect(screen.getByText("VIP")).toBeInTheDocument();

  expect(screen.getByText("48/50")).toBeInTheDocument();

  expect(screen.getByText("Virage")).toBeInTheDocument();

  expect(screen.getByText("22/25")).toBeInTheDocument();

  expect(screen.getByText("25,00 €")).toBeInTheDocument();

  expect(screen.getByText("15,00 €")).toBeInTheDocument();

  expect(calls).toContain("GET /api/v1/admin/organizers/org-1/events");
});
