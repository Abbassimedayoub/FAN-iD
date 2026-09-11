import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

import { OrganizerEventFinalReportPage } from "./OrganizerEventFinalReportPage";

const originalAdapter = httpClient.defaults.adapter;

const organizerUser = {
  id: "user-final-report",
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
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider initialUser={organizerUser}>
        <MemoryRouter initialEntries={["/organizer/events/event-report-1/final-report"]}>
          <Routes>
            <Route
              path="/organizer/events/:eventId/final-report"
              element={<OrganizerEventFinalReportPage />}
            />
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

it("affiche le rapport final complet de l événement", async () => {
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

    if (
      config.method === "get" &&
      config.url === "/api/v1/access/events/event-report-1/final-report"
    ) {
      return response(config, {
        generated_at: "2026-09-11T20:30:00Z",
        tickets: {
          sold_count: 120,
          used_count: 100,
          absent_count: 15,
          voided_count: 5,
        },
        financials: {
          gross_revenue_cents: 300000,
          refunds_cents: 25000,
          net_revenue_cents: 275000,
          commission_cents: 27500,
          organizer_net_cents: 247500,
        },
        scanners: [
          {
            scanner_id: "scanner-1",
            name: "Sam Scanner",
            email: "scanner@example.test",
            scan_count: 100,
            last_scan_at: "2026-09-11T20:00:00Z",
          },
        ],
      });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(await screen.findByRole("heading", { name: "Rapport final" })).toBeInTheDocument();
  expect(screen.getByText("Billets vendus")).toBeInTheDocument();
  expect(screen.getByText("120")).toBeInTheDocument();
  expect(screen.getByText("Synthèse financière")).toBeInTheDocument();
  expect(screen.getByText("Scans par Scanner")).toBeInTheDocument();
  expect(screen.getByText("Sam Scanner")).toBeInTheDocument();
  expect(screen.getByText("100 scan(s)")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Retour à l’événement" })).toHaveAttribute(
    "href",
    "/organizer/events/event-report-1",
  );

  queryClient.clear();
});

it("affiche un état indisponible quand le rapport ne peut pas être chargé", async () => {
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

    if (
      config.method === "get" &&
      config.url === "/api/v1/access/events/event-report-1/final-report"
    ) {
      throw new Error("REPORT_NOT_READY");
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderPage();

  expect(
    await screen.findByRole("heading", { name: "Rapport final indisponible" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Il sera disponible lorsque l’événement aura été clôturé."),
  ).toBeInTheDocument();

  queryClient.clear();
});
