import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAccessToken, getAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import { LoginForm } from "./LoginForm";

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

function fillLoginForm(email: string, password: string): void {
  fireEvent.change(screen.getByLabelText("Adresse e-mail"), {
    target: { value: email },
  });
  fireEvent.change(screen.getByLabelText("Mot de passe"), {
    target: { value: password },
  });
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  clearAccessToken();
});

describe("LoginForm", () => {
  it("validates the form with Zod before calling the API", async () => {
    let loginCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      loginCalls += 1;
      return response(config, 200, {});
    };

    httpClient.defaults.adapter = adapter;

    render(<LoginForm />);

    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(await screen.findByText("Adresse e-mail requise.")).toBeInTheDocument();
    expect(screen.getByText("Mot de passe requis.")).toBeInTheDocument();
    expect(loginCalls).toBe(0);
  });

  it("renders INVALID_CREDENTIALS by error code without attempting a refresh", async () => {
    let loginCalls = 0;
    let refreshCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;
        throw new Error("Le login ne doit jamais déclencher de refresh.");
      }

      if (config.url === "/api/v1/auth/login") {
        loginCalls += 1;

        expect(config.headers.get("Authorization")).toBeUndefined();
        expect(config.data).toBe(
          JSON.stringify({
            email: "fan@example.test",
            password: "MotDePasse-2026",
            client: "web",
          }),
        );

        const unauthorized = response(config, 401, {
          error: {
            code: "INVALID_CREDENTIALS",
            message: "Identifiants invalides",
            details: {},
          },
        });

        throw new AxiosError(
          "Request failed with status code 401",
          "ERR_BAD_REQUEST",
          config,
          undefined,
          unauthorized,
        );
      }

      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("stale-access");

    render(<LoginForm />);
    fillLoginForm("fan@example.test", "MotDePasse-2026");

    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    expect(
      await screen.findByText("Adresse e-mail ou mot de passe incorrect."),
    ).toBeInTheDocument();

    expect(loginCalls).toBe(1);
    expect(refreshCalls).toBe(0);
    expect(getAccessToken()).toBeNull();
  });

  it("stores the access token in memory and returns the authenticated user", async () => {
    const onSuccess = vi.fn();

    const adapter: AxiosAdapter = async (config) => {
      if (config.url !== "/api/v1/auth/login") {
        throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
      }

      return response(config, 200, {
        access: "new-access-token",
        user: {
          id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
          email: "admin@example.test",
          first_name: "Ada",
          last_name: "Admin",
          role: "ADMIN",
          created_at: "2026-08-20T12:00:00Z",
        },
        device: null,
      });
    };

    httpClient.defaults.adapter = adapter;

    render(<LoginForm onSuccess={onSuccess} />);
    fillLoginForm("admin@example.test", "MotDePasse-2026");

    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledTimes(1);
    });

    expect(onSuccess).toHaveBeenCalledWith(
      expect.objectContaining({
        email: "admin@example.test",
        role: "ADMIN",
      }),
    );
    expect(getAccessToken()).toBe("new-access-token");
  });
});

it("renders RATE_LIMIT_EXCEEDED by backend error code", async () => {
  let loginCalls = 0;
  let refreshCalls = 0;

  const adapter: AxiosAdapter = async (config) => {
    if (config.url === "/api/v1/auth/token/refresh") {
      refreshCalls += 1;
      throw new Error("Un 429 de login ne doit jamais déclencher de refresh.");
    }

    if (config.url === "/api/v1/auth/login") {
      loginCalls += 1;

      const throttled = response(config, 429, {
        error: {
          code: "RATE_LIMIT_EXCEEDED",
          message: "Trop de tentatives",
          details: {},
        },
      });

      throw new AxiosError(
        "Request failed with status code 429",
        "ERR_BAD_REQUEST",
        config,
        undefined,
        throttled,
      );
    }

    throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
  };

  httpClient.defaults.adapter = adapter;

  render(<LoginForm />);
  fillLoginForm("fan@example.test", "MotDePasse-2026");

  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

  expect(await screen.findByText("Trop de tentatives. Réessayez plus tard.")).toBeInTheDocument();

  expect(loginCalls).toBe(1);
  expect(refreshCalls).toBe(0);
  expect(getAccessToken()).toBeNull();
});

it("rejects a malformed successful login response without storing an access token", async () => {
  const adapter: AxiosAdapter = async (config) => {
    if (config.url !== "/api/v1/auth/login") {
      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    }

    return response(config, 200, {
      access: "",
      user: {
        id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
        email: "fan@example.test",
        first_name: "Ines",
        last_name: "Bouzid",
        role: "FAN",
        created_at: "2026-08-20T12:00:00Z",
      },
      device: null,
    });
  };

  httpClient.defaults.adapter = adapter;

  render(<LoginForm />);
  fillLoginForm("fan@example.test", "MotDePasse-2026");

  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

  expect(await screen.findByText("Connexion impossible. Réessayez.")).toBeInTheDocument();
  expect(getAccessToken()).toBeNull();
});

it("uses a safe generic message for an unknown backend login error code", async () => {
  const adapter: AxiosAdapter = async (config) => {
    if (config.url !== "/api/v1/auth/login") {
      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    }

    const rejected = response(config, 400, {
      error: {
        code: "FUTURE_LOGIN_ERROR",
        message: "Message backend non destiné à être affiché tel quel",
        details: {},
      },
    });

    throw new AxiosError(
      "Request failed with status code 400",
      "ERR_BAD_REQUEST",
      config,
      undefined,
      rejected,
    );
  };

  httpClient.defaults.adapter = adapter;

  render(<LoginForm />);
  fillLoginForm("fan@example.test", "MotDePasse-2026");

  fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

  expect(await screen.findByText("Connexion impossible. Réessayez.")).toBeInTheDocument();
  expect(getAccessToken()).toBeNull();
});
