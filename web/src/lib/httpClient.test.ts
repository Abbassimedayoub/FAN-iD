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
} from "./httpClient";

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

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  clearAccessToken();
});

describe("httpClient refresh lock", () => {
  it("serializes five concurrent 401 responses behind one refresh", async () => {
    let refreshCalls = 0;
    let protectedCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;

        expect(config.withCredentials).toBe(true);
        expect(config.data).toBe(JSON.stringify({ client: "web" }));

        await new Promise((resolve) => setTimeout(resolve, 10));

        return response(config, 200, {
          access: "fresh-access",
          user: {},
          device: null,
        });
      }

      if (config.url === "/protected") {
        protectedCalls += 1;

        if (config.headers.get("Authorization") !== "Bearer fresh-access") {
          const unauthorized = response(config, 401, {
            error: {
              code: "NOT_AUTHENTICATED",
              message: "Access token expiré",
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

        return response(config, 200, { ok: true });
      }

      throw new Error(`URL inattendue dans le test : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("expired-access");

    const results = await Promise.all(
      Array.from({ length: 5 }, () => httpClient.get("/protected")),
    );

    expect(results).toHaveLength(5);
    expect(results.every((item) => item.status === 200)).toBe(true);
    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(10);
    expect(getAccessToken()).toBe("fresh-access");
  });
});

describe("httpClient refresh failure", () => {
  it("does not recursively refresh when the refresh endpoint returns 401", async () => {
    let refreshCalls = 0;
    let protectedCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;

        expect(config.headers.get("Authorization")).toBeUndefined();

        const unauthorized = response(config, 401, {
          error: {
            code: "TOKEN_INVALID",
            message: "Refresh invalide",
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

      if (config.url === "/protected") {
        protectedCalls += 1;

        const unauthorized = response(config, 401, {
          error: {
            code: "NOT_AUTHENTICATED",
            message: "Access token expiré",
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
    setAccessToken("expired-access");

    await expect(httpClient.get("/protected")).rejects.toMatchObject({
      errorClass: "auth",
      code: "NOT_AUTHENTICATED",
    });

    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(1);
    expect(getAccessToken()).toBeNull();
  });
});

describe("httpClient malformed refresh response", () => {
  it("clears the access token when refresh succeeds without a valid access token", async () => {
    let refreshCalls = 0;
    let protectedCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/token/refresh") {
        refreshCalls += 1;

        return response(config, 200, {
          access: "",
        });
      }

      if (config.url === "/protected") {
        protectedCalls += 1;

        const unauthorized = response(config, 401, {
          error: {
            code: "NOT_AUTHENTICATED",
            message: "Access token expiré",
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
    setAccessToken("expired-access");

    await expect(httpClient.get("/protected")).rejects.toMatchObject({
      errorClass: "auth",
      code: "NOT_AUTHENTICATED",
    });

    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(1);
    expect(getAccessToken()).toBeNull();
  });
});


describe("httpClient invalid session notification", () => {
  it("emits a global invalid-session event when refresh is rejected", async () => {
    let invalidationEvents = 0;

    const listener = (): void => {
      invalidationEvents += 1;
    };

    window.addEventListener(AUTH_SESSION_INVALIDATED_EVENT, listener);

    const adapter: AxiosAdapter = async (config) => {
      if (config.url === "/api/v1/auth/token/refresh") {
        const unauthorized = response(config, 401, {
          error: {
            code: "TOKEN_INVALID",
            message: "Refresh invalide",
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

      if (config.url === "/protected") {
        const unauthorized = response(config, 401, {
          error: {
            code: "NOT_AUTHENTICATED",
            message: "Session invalide",
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
    setAccessToken("revoked-access");

    try {
      await expect(httpClient.get("/protected")).rejects.toMatchObject({
        errorClass: "auth",
      });
    } finally {
      window.removeEventListener(AUTH_SESSION_INVALIDATED_EVENT, listener);
    }

    expect(invalidationEvents).toBe(1);
    expect(getAccessToken()).toBeNull();
  });
});
