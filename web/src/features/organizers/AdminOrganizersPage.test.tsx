import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AppError } from "@/lib/errors";
import { httpClient } from "@/lib/httpClient";

import { AdminOrganizersPage } from "./AdminOrganizersPage";
import { AdminOrganizersView } from "./AdminOrganizersView";
import type { Organizer, OrganizerPage, OrganizerStatus } from "./types";

const originalAdapter = httpClient.defaults.adapter;

function organizer(validationStatus: OrganizerStatus, index: number): Organizer {
  return {
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    org_name: `Organisation ${index}`,
    validation_status: validationStatus,
    commission_rate: "0.1000",
    vat_number: null,
    contact_email: `contact-${index}@example.test`,
    rejection_reason: null,
    validated_at: validationStatus === "APPROVED" ? "2026-08-20T10:00:00Z" : null,
    version: 1,
    created_at: `2026-08-${String(10 + index).padStart(2, "0")}T10:00:00Z`,
    updated_at: `2026-08-${String(10 + index).padStart(2, "0")}T10:00:00Z`,
  };
}

const successPage: OrganizerPage = {
  count: 4,
  next: "http://localhost:8000/api/v1/admin/organizers/?page=2",
  previous: null,
  results: [
    organizer("PENDING", 1),
    organizer("APPROVED", 2),
    organizer("REJECTED", 3),
    organizer("SUSPENDED", 4),
  ],
};

const networkError: AppError = {
  errorClass: "network",
  code: "NETWORK_ERROR",
  message: "Connexion indisponible",
  details: {},
  correlationId: "corr-test-123",
  traceId: null,
  httpStatus: null,
};

const defaultViewProps = {
  validationStatus: "PENDING" as OrganizerStatus | undefined,
  displayedValidationStatus: "PENDING" as OrganizerStatus | undefined,
  data: undefined,
  visiblePage: 1,
  isPending: false,
  isFetching: false,
  error: null,
  showingPreviousData: false,
  onValidationStatusChange: vi.fn(),
  onRetry: vi.fn(),
  onShowAll: vi.fn(),
  onPrevious: vi.fn(),
  onNext: vi.fn(),
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

function serverError(config: InternalAxiosRequestConfig): AxiosError {
  const axiosResponse = response(config, 500, {
    error: {
      code: "INTERNAL_ERROR",
      message: "Erreur interne",
      details: {},
      correlation_id: "corr-500",
    },
  });

  return new AxiosError(
    "Request failed with status code 500",
    "ERR_BAD_RESPONSE",
    config,
    undefined,
    axiosResponse,
  );
}

function createTestQueryClient(): QueryClient {
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

function renderPage(queryClient = createTestQueryClient()) {
  const result = render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AdminOrganizersPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );

  return {
    ...result,
    queryClient,
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
});

describe("AdminOrganizersView - cinq états", () => {
  it("affiche exactement cinq lignes skeleton au chargement initial", () => {
    render(<AdminOrganizersView {...defaultViewProps} isPending isFetching />);

    expect(
      screen.getByRole("table", {
        name: "Chargement des dossiers organisateurs",
      }),
    ).toBeInTheDocument();

    expect(screen.getAllByLabelText(/Chargement de la ligne/)).toHaveLength(5);
  });

  it("conserve la table pendant une actualisation en arrière-plan", () => {
    render(<AdminOrganizersView {...defaultViewProps} data={successPage} isFetching />);

    expect(screen.getByText("Actualisation des dossiers…")).toBeInTheDocument();

    expect(screen.getByText("Organisation 1")).toBeInTheDocument();

    expect(screen.queryByLabelText("Chargement de la ligne 1")).not.toBeInTheDocument();
  });

  it("affiche l'état vide des demandes en attente avec accès à toutes les demandes", () => {
    const onShowAll = vi.fn();

    render(
      <AdminOrganizersView
        {...defaultViewProps}
        data={{
          count: 0,
          next: null,
          previous: null,
          results: [],
        }}
        onShowAll={onShowAll}
      />,
    );

    expect(screen.getByText("Aucune demande en attente")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Voir toutes les demandes",
      }),
    );

    expect(onShowAll).toHaveBeenCalledTimes(1);
  });

  it("affiche l'erreur finale avec Réessayer lorsqu'aucune donnée n'est disponible", () => {
    const onRetry = vi.fn();

    render(<AdminOrganizersView {...defaultViewProps} error={networkError} onRetry={onRetry} />);

    expect(screen.getByText("Connexion indisponible. Vérifiez votre réseau.")).toBeInTheDocument();

    expect(screen.getByText("Référence : corr-test-123")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Réessayer",
      }),
    );

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("affiche la table, les quatre statuts et la pagination en succès", () => {
    const onNext = vi.fn();

    render(<AdminOrganizersView {...defaultViewProps} data={successPage} onNext={onNext} />);

    const table = screen.getByRole("table", {
      name: "Dossiers organisateurs",
    });

    expect(table).toBeInTheDocument();

    expect(within(table).getByText("En attente")).toBeInTheDocument();
    expect(within(table).getByText("Approuvé")).toBeInTheDocument();
    expect(within(table).getByText("Rejeté")).toBeInTheDocument();
    expect(within(table).getByText("Suspendu")).toBeInTheDocument();

    expect(screen.getByText("Page 1 · 4 dossiers")).toBeInTheDocument();

    expect(
      screen.getByRole("button", {
        name: "Précédent",
      }),
    ).toBeDisabled();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Suivant",
      }),
    );

    expect(onNext).toHaveBeenCalledTimes(1);
  });

  it("conserve la table précédente et affiche un bandeau lorsqu'une requête échoue", () => {
    render(
      <AdminOrganizersView
        {...defaultViewProps}
        data={successPage}
        error={networkError}
        showingPreviousData
      />,
    );

    expect(screen.getByText("Connexion indisponible. Vérifiez votre réseau.")).toBeInTheDocument();

    expect(
      screen.getByText("Les dernières données disponibles restent affichées."),
    ).toBeInTheDocument();

    expect(screen.getByText("Organisation 1")).toBeInTheDocument();
  });

  it("transmet les changements de filtre sans effectuer elle-même de requête réseau", () => {
    const onValidationStatusChange = vi.fn();

    render(
      <AdminOrganizersView
        {...defaultViewProps}
        data={successPage}
        onValidationStatusChange={onValidationStatusChange}
      />,
    );

    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Statut",
      }),
      {
        target: {
          value: "APPROVED",
        },
      },
    );

    expect(onValidationStatusChange).toHaveBeenLastCalledWith("APPROVED");

    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Statut",
      }),
      {
        target: {
          value: "",
        },
      },
    );

    expect(onValidationStatusChange).toHaveBeenLastCalledWith(undefined);
  });
});

describe("AdminOrganizersPage - intégration TanStack Query", () => {
  it("appelle la liste avec le filtre PENDING puis transmet le filtre APPROVED exact", async () => {
    const calls: Array<{
      url: string | undefined;
      params: unknown;
    }> = [];

    const adapter: AxiosAdapter = async (config) => {
      calls.push({
        url: config.url,
        params: config.params,
      });

      return response(config, 200, {
        count: 1,
        next: null,
        previous: null,
        results: [
          organizer(
            config.params?.["validation_status"] === "APPROVED" ? "APPROVED" : "PENDING",
            calls.length,
          ),
        ],
      });
    };

    httpClient.defaults.adapter = adapter;

    const { queryClient } = renderPage();

    await screen.findByText("Organisation 1");

    expect(calls[0]).toEqual({
      url: "/api/v1/admin/organizers/",
      params: {
        page: 1,
        validation_status: "PENDING",
      },
    });

    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Statut",
      }),
      {
        target: {
          value: "APPROVED",
        },
      },
    );

    await waitFor(() => {
      expect(calls).toHaveLength(2);
    });

    expect(calls[1]).toEqual({
      url: "/api/v1/admin/organizers/",
      params: {
        page: 1,
        validation_status: "APPROVED",
      },
    });

    queryClient.clear();
  });

  it("garde la page précédente visible si la page suivante échoue", async () => {
    let rejectSecondPage: ((reason?: unknown) => void) | null = null;

    const firstPage: OrganizerPage = {
      count: 21,
      next: "http://localhost:8000/api/v1/admin/organizers/?page=2",
      previous: null,
      results: [organizer("PENDING", 1)],
    };

    const adapter: AxiosAdapter = async (config) => {
      const requestedPage = Number(config.params?.["page"] ?? 1);

      if (requestedPage === 1) {
        return response(config, 200, firstPage);
      }

      if (requestedPage === 2) {
        return new Promise<AxiosResponse>((_resolve, reject) => {
          rejectSecondPage = reject;
        });
      }

      throw new Error(`Page inattendue : ${requestedPage}`);
    };

    httpClient.defaults.adapter = adapter;

    const { queryClient } = renderPage();

    await screen.findByText("Organisation 1");

    expect(screen.getByText("Page 1 · 21 dossiers")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Suivant",
      }),
    );

    await screen.findByText("Actualisation des dossiers…");

    expect(screen.getByText("Organisation 1")).toBeInTheDocument();
    expect(screen.getByText("Page 1 · 21 dossiers")).toBeInTheDocument();

    await waitFor(() => {
      expect(rejectSecondPage).not.toBeNull();
    });

    await act(async () => {
      rejectSecondPage?.(
        serverError({
          ...({
            headers: {},
            method: "get",
            url: "/api/v1/admin/organizers/",
            params: {
              page: 2,
              validation_status: "PENDING",
            },
          } as InternalAxiosRequestConfig),
        }),
      );

      await Promise.resolve();
    });

    await screen.findByText("Un problème est survenu de notre côté.");

    expect(
      screen.getByText("Les dernières données disponibles restent affichées."),
    ).toBeInTheDocument();

    expect(screen.getByText("Organisation 1")).toBeInTheDocument();
    expect(screen.getByText("Page 1 · 21 dossiers")).toBeInTheDocument();

    queryClient.clear();
  });
  it("passe de l'état vide PENDING à toutes les demandes", async () => {
    const calls: unknown[] = [];

    const adapter: AxiosAdapter = async (config) => {
      calls.push(config.params);

      if (config.params?.["validation_status"] === "PENDING") {
        return response(config, 200, {
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }

      return response(config, 200, {
        count: 1,
        next: null,
        previous: null,
        results: [organizer("APPROVED", 2)],
      });
    };

    httpClient.defaults.adapter = adapter;

    const { queryClient } = renderPage();

    await screen.findByText("Aucune demande en attente");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Voir toutes les demandes",
      }),
    );

    await screen.findByText("Organisation 2");

    expect(calls).toHaveLength(2);
    expect(calls[1]).toEqual({
      page: 1,
    });

    queryClient.clear();
  });

  it("revient de la page 2 à la page précédente", async () => {
    const requestedPages: number[] = [];

    const adapter: AxiosAdapter = async (config) => {
      const requestedPage = Number(config.params?.["page"] ?? 1);
      requestedPages.push(requestedPage);

      if (requestedPage === 1) {
        return response(config, 200, {
          count: 21,
          next: "http://localhost:8000/api/v1/admin/organizers/?page=2",
          previous: null,
          results: [organizer("PENDING", 1)],
        });
      }

      return response(config, 200, {
        count: 21,
        next: null,
        previous: "http://localhost:8000/api/v1/admin/organizers/?page=1",
        results: [organizer("PENDING", 2)],
      });
    };

    httpClient.defaults.adapter = adapter;

    const { queryClient } = renderPage();

    await screen.findByText("Organisation 1");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Suivant",
      }),
    );

    await screen.findByText("Organisation 2");
    expect(screen.getByText("Page 2 · 21 dossiers")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Précédent",
      }),
    );

    await waitFor(() => {
      expect(screen.getByText("Page 1 · 21 dossiers")).toBeInTheDocument();
    });

    expect(requestedPages.filter((page) => page === 1).length).toBeGreaterThanOrEqual(1);

    queryClient.clear();
  });

  it("conserve le filtre précédent après erreur puis réessaie le filtre demandé", async () => {
    let approvedAttempts = 0;

    const adapter: AxiosAdapter = async (config) => {
      const status = config.params?.["validation_status"];

      if (status === "PENDING") {
        return response(config, 200, {
          count: 1,
          next: null,
          previous: null,
          results: [organizer("PENDING", 1)],
        });
      }

      if (status === "APPROVED") {
        approvedAttempts += 1;

        if (approvedAttempts === 1) {
          throw serverError(config);
        }

        return response(config, 200, {
          count: 1,
          next: null,
          previous: null,
          results: [organizer("APPROVED", 2)],
        });
      }

      throw new Error(`Filtre inattendu : ${String(status)}`);
    };

    httpClient.defaults.adapter = adapter;

    const { queryClient } = renderPage();

    await screen.findByText("Organisation 1");

    fireEvent.change(
      screen.getByRole("combobox", {
        name: "Statut",
      }),
      {
        target: {
          value: "APPROVED",
        },
      },
    );

    await screen.findByText("Un problème est survenu de notre côté.");

    expect(
      screen.getByText("Les dernières données disponibles restent affichées."),
    ).toBeInTheDocument();

    expect(screen.getByText("Organisation 1")).toBeInTheDocument();
    expect(screen.getByText("Page 1 · 1 dossier")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Réessayer",
      }),
    );

    await screen.findByText("Organisation 2");

    expect(approvedAttempts).toBe(2);

    queryClient.clear();
  });
});
