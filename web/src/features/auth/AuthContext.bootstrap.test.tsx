import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, describe, expect, it } from "vitest";

import {
  AUTH_SESSION_INVALIDATED_EVENT,
  clearAccessToken,
  getAccessToken,
  httpClient,
  setAccessToken,
} from "@/lib/httpClient";

import { AuthProvider, useAuth } from "./AuthContext";
import { getCurrentUser } from "./session";

const originalAdapter = httpClient.defaults.adapter;

function response(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown,
): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: status === 200 ? "OK" : "Unauthorized",
  };
}

function unauthorized(config: InternalAxiosRequestConfig): AxiosError {
  return new AxiosError(
    "Request failed with status code 401",
    "ERR_BAD_REQUEST",
    config,
    undefined,
    response(config, 401, {
      error: {
        code: "NOT_AUTHENTICATED",
        message: "Authentification requise",
        details: {},
      },
    }),
  );
}

function AuthProbe() {
  const { status, user, clearAuthentication } = useAuth();

  return (
    <>
      <p data-testid="auth-status">{status}</p>
      <p data-testid="auth-user">{user?.email ?? "anonymous"}</p>
      <button type="button" onClick={clearAuthentication}>
        Effacer l’authentification
      </button>
    </>
  );
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  clearAccessToken();
  window.localStorage.clear();
});

describe("AuthProvider bootstrap", () => {
  it("starts anonymous when no browser session cookie can be restored", async () => {
    let meCalls = 0;
    let refreshCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/me") {
        meCalls += 1;
        throw unauthorized(config);
      }

      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;
        throw unauthorized(config);
      }

      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("anonymous");
    });

    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");
    expect(meCalls).toBe(1);
    expect(refreshCalls).toBe(1);
    expect(getAccessToken()).toBeNull();
  });

  it("restores the web session while the current browser session is active", async () => {
    let meCalls = 0;
    let refreshCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;

        expect(config.headers.get("Authorization")).toBeUndefined();
        expect(config.data).toBe(JSON.stringify({ client: "web" }));

        return response(config, 200, {
          access: "restored-access",
        });
      }

      if (config.url === "/api/v1/auth/me") {
        meCalls += 1;

        if (meCalls === 1) {
          expect(config.headers.get("Authorization")).toBeUndefined();
          throw unauthorized(config);
        }

        expect(config.headers.get("Authorization")).toBe("Bearer restored-access");

        return response(config, 200, {
          id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
          email: "admin@example.test",
          first_name: "Ada",
          last_name: "Admin",
          phone: null,
          date_of_birth: "1990-01-01",
          role: "ADMIN",
          created_at: "2026-08-20T12:00:00Z",
          updated_at: "2026-08-20T12:00:00Z",
          version: 1,
        });
      }

      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Restauration de la session");

    expect(await screen.findByText("admin@example.test")).toBeInTheDocument();
    expect(screen.getByText("authenticated")).toBeInTheDocument();

    expect(meCalls).toBe(2);
    expect(refreshCalls).toBe(1);
    expect(getAccessToken()).toBe("restored-access");
  });

  it("becomes anonymous when the current browser session can no longer refresh", async () => {
    let meCalls = 0;
    let refreshCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/me") {
        meCalls += 1;
        throw unauthorized(config);
      }

      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;
        throw unauthorized(config);
      }

      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("anonymous");
    });
    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");

    expect(meCalls).toBe(1);
    expect(refreshCalls).toBe(1);
    expect(getAccessToken()).toBeNull();
  });

  it("fails closed on a malformed /auth/me identity", async () => {
    setAccessToken("existing-access");

    const adapter: AxiosAdapter = async (config) => {
      if (config.url !== "/api/v1/auth/me") {
        throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
      }

      expect(config.headers.get("Authorization")).toBe("Bearer existing-access");

      return response(config, 200, {
        id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
        email: "root@example.test",
        first_name: "Root",
        last_name: "Invalid",
        role: "ROOT",
        created_at: "2026-08-20T12:00:00Z",
      });
    };

    httpClient.defaults.adapter = adapter;

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-status")).toHaveTextContent("anonymous");
    });
    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");

    expect(getAccessToken()).toBeNull();
  });
});

it("rejects a non-object /auth/me payload", async () => {
  const adapter: AxiosAdapter = async (config) => {
    if (config.url !== "/api/v1/auth/me") {
      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    }

    return response(config, 200, null);
  };

  httpClient.defaults.adapter = adapter;

  await expect(getCurrentUser()).rejects.toThrow("Réponse /auth/me invalide.");
});

it("ignores a late bootstrap failure after the provider is unmounted", async () => {
  let rejectRequest: ((reason?: unknown) => void) | null = null;

  const adapter: AxiosAdapter = async () =>
    new Promise<AxiosResponse>((_resolve, reject) => {
      rejectRequest = reject;
    });

  httpClient.defaults.adapter = adapter;
  setAccessToken("still-live-access");
  const { unmount } = render(
    <AuthProvider>
      <AuthProbe />
    </AuthProvider>,
  );

  await waitFor(() => {
    expect(rejectRequest).not.toBeNull();
  });

  unmount();

  await act(async () => {
    rejectRequest?.(new Error("late bootstrap failure"));
    await new Promise((resolve) => setTimeout(resolve, 0));
  });

  expect(getAccessToken()).toBe("still-live-access");
});

describe("AuthProvider local authentication cleanup", () => {
  it("efface le bearer et repasse immédiatement en anonymous", () => {
    setAccessToken("current-access");

    render(
      <AuthProvider
        initialUser={{
          id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
          email: "admin@example.test",
          first_name: "Ada",
          last_name: "Admin",
          role: "ADMIN",
          created_at: "2026-08-20T12:00:00Z",
        }}
      >
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("auth-status")).toHaveTextContent("authenticated");

    expect(screen.getByTestId("auth-user")).toHaveTextContent("admin@example.test");

    expect(getAccessToken()).toBe("current-access");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Effacer l’authentification",
      }),
    );

    expect(screen.getByTestId("auth-status")).toHaveTextContent("anonymous");

    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");

    expect(getAccessToken()).toBeNull();
  });
});


describe("AuthProvider session security", () => {
  const authenticatedUser = {
    id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
    email: "admin@example.test",
    first_name: "Ada",
    last_name: "Admin",
    role: "ADMIN" as const,
    created_at: "2026-08-20T12:00:00Z",
  };

  it("expires an authenticated web session after 15 minutes of inactivity", async () => {
    let logoutCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/logout") {
        logoutCalls += 1;
        return response(config, 200, {});
      }

      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("current-access");

    render(
      <AuthProvider initialUser={authenticatedUser} inactivityTimeoutMs={40}>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("auth-status")).toHaveTextContent("authenticated");

    await waitFor(
      () => {
        expect(screen.getByTestId("auth-status")).toHaveTextContent("anonymous");
      },
      { timeout: 1000 },
    );

    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");
    expect(getAccessToken()).toBeNull();

    await waitFor(() => {
      expect(logoutCalls).toBe(1);
    });
  });

  it("becomes anonymous immediately when the HTTP layer invalidates the session", () => {
    setAccessToken("revoked-access");

    render(
      <AuthProvider initialUser={authenticatedUser}>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByTestId("auth-status")).toHaveTextContent("authenticated");

    act(() => {
      window.dispatchEvent(new Event(AUTH_SESSION_INVALIDATED_EVENT));
    });

    expect(screen.getByTestId("auth-status")).toHaveTextContent("anonymous");
    expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous");
    expect(getAccessToken()).toBeNull();
  });
});
