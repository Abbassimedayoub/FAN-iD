import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AppError } from "@/lib/errors";
import { httpClient } from "@/lib/httpClient";

import { AdminOrganizerDetailPage } from "./AdminOrganizerDetailPage";
import { AdminOrganizersPage } from "./AdminOrganizersPage";
import { AdminOrganizerDetailView } from "./AdminOrganizerDetailView";
import type { Organizer } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const ORGANIZER_ID = "00000000-0000-4000-8000-000000000001";

const organizer: Organizer = {
  id: ORGANIZER_ID,
  org_name: "Association Lumière",
  validation_status: "PENDING",
  commission_rate: "0.1000",
  vat_number: null,
  contact_email: "contact@example.test",
  rejection_reason: null,
  validated_at: null,
  version: 4,
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-20T10:00:00Z",
};

const notFoundError: AppError = {
  errorClass: "not_found",
  code: "NOT_FOUND",
  message: "Ressource introuvable",
  details: {},
  correlationId: "corr-404",
  traceId: null,
  httpStatus: 404,
};

const networkError: AppError = {
  errorClass: "network",
  code: "NETWORK_ERROR",
  message: "Connexion indisponible",
  details: {},
  correlationId: "corr-network",
  traceId: null,
  httpStatus: null,
};

function response<T>(
  config: InternalAxiosRequestConfig,
  status: number,
  data: T,
): AxiosResponse<T> {
  return {
    config,
    data,
    headers: {},
    status,
    statusText: String(status),
  };
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderPage(queryClient = createQueryClient()) {
  return render(
    <MemoryRouter initialEntries={[`/admin/organizers/${ORGANIZER_ID}`]}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/admin/organizers/:organizerId" element={<AdminOrganizerDetailPage />} />
          <Route path="/admin/organizers" element={<div>Liste des demandes</div>} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
});

describe("AdminOrganizerDetailView", () => {
  it("affiche un skeleton de fiche au chargement initial", () => {
    render(
      <AdminOrganizerDetailView
        data={undefined}
        isPending
        isFetching
        error={null}
        onRetry={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Chargement du dossier organisateur")).toBeInTheDocument();

    expect(screen.queryByText("Association Lumière")).not.toBeInTheDocument();
  });

  it("conserve la fiche pendant une actualisation", () => {
    render(
      <AdminOrganizerDetailView
        data={organizer}
        isPending={false}
        isFetching
        error={null}
        onRetry={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText("Association Lumière")).toBeInTheDocument();
    expect(screen.getByText("Actualisation du dossier…")).toBeInTheDocument();
  });

  it("affiche le 404 métier exact avec retour", () => {
    const onBack = vi.fn();

    render(
      <AdminOrganizerDetailView
        data={undefined}
        isPending={false}
        isFetching={false}
        error={notFoundError}
        onRetry={vi.fn()}
        onBack={onBack}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Cette demande n’existe plus",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Retour aux demandes",
      }),
    );

    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("affiche une erreur générique avec retry et correlation id", () => {
    const onRetry = vi.fn();

    render(
      <AdminOrganizerDetailView
        data={undefined}
        isPending={false}
        isFetching={false}
        error={networkError}
        onRetry={onRetry}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText("Connexion indisponible. Vérifiez votre réseau.")).toBeInTheDocument();

    expect(screen.getByText("Référence : corr-network")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Réessayer",
      }),
    );

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("affiche les champs manquants avec un tiret cadratin", () => {
    render(
      <AdminOrganizerDetailView
        data={organizer}
        isPending={false}
        isFetching={false}
        error={null}
        onRetry={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText("Association Lumière")).toBeInTheDocument();
    expect(screen.getByText("contact@example.test")).toBeInTheDocument();
    expect(screen.getByText("10 %")).toBeInTheDocument();
    expect(screen.getByText("En attente")).toBeInTheDocument();

    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });
});

describe("AdminOrganizerDetailPage", () => {
  it("appelle exactement le GET admin detail et affiche la réponse", async () => {
    const calls: string[] = [];

    const adapter: AxiosAdapter = async (config) => {
      calls.push(config.url ?? "");

      return response(config, 200, organizer);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    await screen.findByText("Association Lumière");

    expect(calls).toContain(`/api/v1/admin/organizers/${ORGANIZER_ID}`);

    expect(calls).toContain(`/api/v1/admin/organizers/${ORGANIZER_ID}/events`);
  });

  it("revient vers la liste depuis la fiche", async () => {
    const adapter: AxiosAdapter = async (config) => response(config, 200, organizer);

    httpClient.defaults.adapter = adapter;

    renderPage();

    await screen.findByText("Association Lumière");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Retour aux demandes",
      }),
    );

    expect(await screen.findByText("Liste des demandes")).toBeInTheDocument();
  });

  it("rend le 404 spécialisé renvoyé par l'API", async () => {
    const adapter: AxiosAdapter = async (config) => {
      const axiosResponse = response(config, 404, {
        error: {
          code: "NOT_FOUND",
          message: "Ressource introuvable",
          details: {},
          correlation_id: "corr-api-404",
        },
      });

      throw new AxiosError(
        "Request failed with status code 404",
        "ERR_BAD_REQUEST",
        config,
        undefined,
        axiosResponse,
      );
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    expect(
      await screen.findByRole("heading", {
        name: "Cette demande n’existe plus",
      }),
    ).toBeInTheDocument();
  });
});

describe("navigation depuis OrganizerTable", () => {
  it("transmet l'identifiant du dossier sélectionné", async () => {
    const onOpenOrganizer = vi.fn();

    const { OrganizerTable } = await import("./OrganizerTable");

    render(<OrganizerTable organizers={[organizer]} onOpenOrganizer={onOpenOrganizer} />);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Association Lumière",
      }),
    );

    expect(onOpenOrganizer).toHaveBeenCalledWith(ORGANIZER_ID);
  });
});

describe("couverture des branches organizer detail", () => {
  it("réessaie le GET detail depuis la page après une erreur", async () => {
    let calls = 0;

    const adapter: AxiosAdapter = async (config) => {
      calls += 1;

      if (calls === 1) {
        const axiosResponse = response(config, 500, {
          error: {
            code: "INTERNAL_ERROR",
            message: "Erreur interne",
            details: {},
            correlation_id: "corr-retry",
          },
        });

        throw new AxiosError(
          "Request failed with status code 500",
          "ERR_BAD_RESPONSE",
          config,
          undefined,
          axiosResponse,
        );
      }

      return response(config, 200, organizer);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Réessayer",
      }),
    );

    expect(await screen.findByText("Association Lumière")).toBeInTheDocument();
    expect(calls).toBe(3);
  });

  it("conserve une commission non numérique telle quelle", () => {
    render(
      <AdminOrganizerDetailView
        data={{
          ...organizer,
          commission_rate: "indisponible",
        }}
        isPending={false}
        isFetching={false}
        error={null}
        onRetry={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText("indisponible")).toBeInTheDocument();
  });

  it("ne rend rien lorsqu'aucune donnée ni erreur n'est disponible", () => {
    const { container } = render(
      <AdminOrganizerDetailView
        data={undefined}
        isPending={false}
        isFetching={false}
        error={null}
        onRetry={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("navigue réellement de la liste admin vers la fiche", async () => {
    const adapter: AxiosAdapter = async (config) =>
      response(config, 200, {
        count: 1,
        next: null,
        previous: null,
        results: [organizer],
      });

    httpClient.defaults.adapter = adapter;

    render(
      <MemoryRouter initialEntries={["/admin/organizers"]}>
        <QueryClientProvider client={createQueryClient()}>
          <Routes>
            <Route path="/admin/organizers" element={<AdminOrganizersPage />} />
            <Route
              path="/admin/organizers/:organizerId"
              element={<div>Fiche organisateur atteinte</div>}
            />
          </Routes>
        </QueryClientProvider>
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Association Lumière",
      }),
    );

    expect(await screen.findByText("Fiche organisateur atteinte")).toBeInTheDocument();
  });
});
