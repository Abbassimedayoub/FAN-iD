import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import type { AuthUser } from "@/features/auth/types";
import { clearAccessToken, getAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import { SessionsPage } from "./SessionsPage";
import type { AuthSession } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const adminUser: AuthUser = {
  id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
  email: "admin@example.test",
  first_name: "Ada",
  last_name: "Admin",
  role: "ADMIN",
  created_at: "2026-08-20T12:00:00Z",
};

const currentSession: AuthSession = {
  id: "00000000-0000-4000-8000-000000000001",
  device: {
    id: "10000000-0000-4000-8000-000000000001",
    label: "MacBook Pro",
  },
  ip: "203.0.113.7",
  user_agent: "Chrome sur macOS",
  issued_at: "2026-08-22T10:00:00Z",
  last_used_at: "2026-08-22T12:30:00Z",
  expires_at: "2026-09-21T10:00:00Z",
  current: true,
};

const otherSession: AuthSession = {
  id: "00000000-0000-4000-8000-000000000002",
  device: {
    id: "10000000-0000-4000-8000-000000000002",
    label: "iPhone",
  },
  ip: "198.51.100.9",
  user_agent: "Safari sur iOS",
  issued_at: "2026-08-20T08:00:00Z",
  last_used_at: "2026-08-21T09:15:00Z",
  expires_at: "2026-09-19T08:00:00Z",
  current: false,
};

function response<T>(
  config: InternalAxiosRequestConfig,
  status: number,
  data: T,
): AxiosResponse<T> {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: String(status),
  };
}

function serverError(config: InternalAxiosRequestConfig): AxiosError {
  return new AxiosError(
    "Request failed with status code 500",
    "ERR_BAD_RESPONSE",
    config,
    undefined,
    response(config, 500, {
      error: {
        code: "INTERNAL_ERROR",
        message: "Erreur serveur",
        details: {},
        correlation_id: "corr-sessions-500",
      },
    }),
  );
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
  const result = render(
    <MemoryRouter initialEntries={["/sessions"]}>
      <QueryClientProvider client={queryClient}>
        <AuthProvider initialUser={adminUser}>
          <Routes>
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/login" element={<h1>Connexion</h1>} />
            <Route path="/admin/organizers" element={<h1>Organisateurs admin</h1>} />
          </Routes>
        </AuthProvider>
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
  clearAccessToken();
});

describe("SessionsPage", () => {
  it("affiche la navigation administrateur complète sur la page sessions", async () => {
    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get" && config.url === "/api/v1/auth/sessions") {
        return response(config, 200, [currentSession]);
      }

      throw new Error(
        `Requête inattendue : ${config.method ?? "<vide>"} ${config.url ?? "<vide>"}`,
      );
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("access-token");

    renderPage();

    expect(await screen.findByText("MacBook Pro")).toBeInTheDocument();

    expect(
      screen.getByRole("navigation", { name: "Navigation administrateur" }),
    ).toBeInTheDocument();

    expect(screen.getAllByRole("link", { name: "Organisateurs" }).length).toBeGreaterThan(0);

    expect(screen.getAllByRole("link", { name: "Sécurité" }).length).toBeGreaterThan(0);

    expect(screen.getAllByRole("link", { name: "Sessions" }).length).toBeGreaterThan(0);

    expect(screen.getByRole("button", { name: "Se déconnecter" })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "← Retour" })).not.toBeInTheDocument();

    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("admin@example.test")).toBeInTheDocument();
  });

  it("ferme la session avec le endpoint logout puis redirige vers la connexion", async () => {
    let logoutCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get" && config.url === "/api/v1/auth/sessions") {
        return response(config, 200, [currentSession]);
      }

      if (config.method === "post" && config.url === "/api/v1/auth/logout") {
        logoutCalls += 1;
        return response(config, 204, undefined);
      }

      throw new Error(
        `Requête inattendue : ${config.method ?? "<vide>"} ${config.url ?? "<vide>"}`,
      );
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("current-access");

    const queryClient = createQueryClient();
    queryClient.setQueryData(["private-account"], { secret: true });

    renderPage(queryClient);

    expect(await screen.findByText("MacBook Pro")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Se déconnecter" }));

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();

    expect(logoutCalls).toBe(1);
    expect(getAccessToken()).toBeNull();

    await waitFor(() => {
      expect(queryClient.getQueryCache().getAll()).toHaveLength(0);
    });
  });

  it("révoque une session distante puis recharge la liste sans effacer l’authentification", async () => {
    let getCalls = 0;
    let deleteCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get" && config.url === "/api/v1/auth/sessions") {
        getCalls += 1;

        return response(
          config,
          200,
          getCalls === 1 ? [currentSession, otherSession] : [currentSession],
        );
      }

      if (config.method === "delete" && config.url === `/api/v1/auth/sessions/${otherSession.id}`) {
        deleteCalls += 1;
        return response(config, 204, undefined);
      }

      throw new Error(
        `Requête inattendue : ${config.method ?? "<vide>"} ${config.url ?? "<vide>"}`,
      );
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("access-token");

    renderPage();

    expect(await screen.findByText("iPhone")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Révoquer",
      }),
    );

    await waitFor(() => {
      expect(deleteCalls).toBe(1);
    });

    await waitFor(() => {
      expect(getCalls).toBe(2);
      expect(screen.queryByText("iPhone")).not.toBeInTheDocument();
    });

    expect(getAccessToken()).toBe("access-token");

    expect(
      screen.getByRole("heading", {
        name: "Mes sessions",
      }),
    ).toBeInTheDocument();
  });

  it("révoque la session courante, nettoie l’authentification et redirige vers login sans refetch", async () => {
    let getCalls = 0;
    let deleteCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get" && config.url === "/api/v1/auth/sessions") {
        getCalls += 1;
        return response(config, 200, [currentSession]);
      }

      if (
        config.method === "delete" &&
        config.url === `/api/v1/auth/sessions/${currentSession.id}`
      ) {
        deleteCalls += 1;
        return response(config, 204, undefined);
      }

      throw new Error(
        `Requête inattendue : ${config.method ?? "<vide>"} ${config.url ?? "<vide>"}`,
      );
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("current-access");

    const queryClient = createQueryClient();
    const previousAccountQueryKey = ["previous-account", "private-data"] as const;

    queryClient.setQueryData(previousAccountQueryKey, { secret: "cached-data" });

    renderPage(queryClient);

    expect(queryClient.getQueryData(previousAccountQueryKey)).toEqual({ secret: "cached-data" });

    expect(await screen.findByText("MacBook Pro")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Déconnecter cette session",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Connexion",
      }),
    ).toBeInTheDocument();

    expect(deleteCalls).toBe(1);
    expect(getCalls).toBe(1);
    expect(getAccessToken()).toBeNull();

    expect(queryClient.getQueryData(previousAccountQueryKey)).toBeUndefined();

    expect(queryClient.getQueryCache().getAll()).toHaveLength(0);

    expect(queryClient.getMutationCache().getAll()).toHaveLength(0);
  });

  it("permet de réessayer la liste après une erreur serveur", async () => {
    let getCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method !== "get" || config.url !== "/api/v1/auth/sessions") {
        throw new Error(
          `Requête inattendue : ${config.method ?? "<vide>"} ${config.url ?? "<vide>"}`,
        );
      }

      getCalls += 1;

      if (getCalls === 1) {
        throw serverError(config);
      }

      return response(config, 200, [currentSession]);
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("access-token");

    renderPage();

    expect(await screen.findByText("Un problème est survenu de notre côté.")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Réessayer",
      }),
    );

    expect(await screen.findByText("MacBook Pro")).toBeInTheDocument();

    expect(getCalls).toBe(2);
    expect(getAccessToken()).toBe("access-token");
  });

  it("conserve la liste et l’authentification lorsqu’une révocation échoue", async () => {
    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get" && config.url === "/api/v1/auth/sessions") {
        return response(config, 200, [currentSession, otherSession]);
      }

      if (config.method === "delete" && config.url === `/api/v1/auth/sessions/${otherSession.id}`) {
        throw serverError(config);
      }

      throw new Error(
        `Requête inattendue : ${config.method ?? "<vide>"} ${config.url ?? "<vide>"}`,
      );
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("access-token");

    renderPage();

    expect(await screen.findByText("iPhone")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Révoquer",
      }),
    );

    expect(await screen.findByText("Un problème est survenu de notre côté.")).toBeInTheDocument();

    expect(screen.getByText("iPhone")).toBeInTheDocument();

    expect(getAccessToken()).toBe("access-token");
  });
});
