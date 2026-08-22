import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError, type AxiosAdapter, type AxiosResponse } from "axios";
import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import type { AuthSession } from "./types";
import { useRevokeSession } from "./useRevokeSession";
import { sessionsQueryKey, useSessions } from "./useSessions";

function response(
  config: Parameters<AxiosAdapter>[0],
  status: number,
  data: unknown,
): AxiosResponse {
  return {
    data,
    status,
    statusText: status === 204 ? "No Content" : "OK",
    headers: {},
    config,
  };
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const currentSession: AuthSession = {
  id: "00000000-0000-4000-8000-000000000001",
  device: null,
  ip: "203.0.113.7",
  user_agent: "FAN-iD Web",
  issued_at: "2026-08-22T10:00:00Z",
  last_used_at: "2026-08-22T12:00:00Z",
  expires_at: "2026-09-21T10:00:00Z",
  current: true,
};

const otherSession: AuthSession = {
  ...currentSession,
  id: "00000000-0000-4000-8000-000000000002",
  current: false,
};

describe("sessions hooks", () => {
  afterEach(() => {
    clearAccessToken();
    httpClient.defaults.adapter = undefined;
    vi.restoreAllMocks();
  });

  it("charge les sessions avec la query key dédiée", async () => {
    const queryClient = createQueryClient();

    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("get");
      expect(config.url).toBe("/api/v1/auth/sessions");

      return response(config, 200, [currentSession, otherSession]);
    };

    setAccessToken("access-token");
    httpClient.defaults.adapter = adapter;

    const { result } = renderHook(() => useSessions(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual([currentSession, otherSession]);

    expect(queryClient.getQueryData(sessionsQueryKey)).toEqual([currentSession, otherSession]);
  });

  it("révoque une session distante puis invalide la liste", async () => {
    const queryClient = createQueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");

    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("delete");
      expect(config.url).toBe(`/api/v1/auth/sessions/${otherSession.id}`);

      return response(config, 204, undefined);
    };

    setAccessToken("access-token");
    httpClient.defaults.adapter = adapter;

    const { result } = renderHook(() => useRevokeSession(), {
      wrapper: createWrapper(queryClient),
    });

    await result.current.mutateAsync({
      sessionId: otherSession.id,
      current: false,
    });

    expect(invalidateQueries).toHaveBeenCalledTimes(1);
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: sessionsQueryKey,
    });
  });

  it("signale la révocation de la session courante sans refetch", async () => {
    const queryClient = createQueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const onCurrentSessionRevoked = vi.fn();

    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("delete");
      expect(config.url).toBe(`/api/v1/auth/sessions/${currentSession.id}`);

      return response(config, 204, undefined);
    };

    setAccessToken("access-token");
    httpClient.defaults.adapter = adapter;

    const { result } = renderHook(
      () =>
        useRevokeSession({
          onCurrentSessionRevoked,
        }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    await result.current.mutateAsync({
      sessionId: currentSession.id,
      current: true,
    });

    expect(onCurrentSessionRevoked).toHaveBeenCalledTimes(1);
    expect(invalidateQueries).not.toHaveBeenCalled();
  });

  it("ne signale pas une révocation courante qui échoue", async () => {
    const queryClient = createQueryClient();
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries");
    const onCurrentSessionRevoked = vi.fn();

    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("delete");

      throw new AxiosError(
        "Request failed with status code 500",
        "ERR_BAD_RESPONSE",
        config,
        undefined,
        response(config, 500, {
          error: {
            code: "INTERNAL_ERROR",
            message: "Erreur serveur",
            details: {},
            correlation_id: "corr-500",
          },
        }),
      );
    };

    setAccessToken("access-token");
    httpClient.defaults.adapter = adapter;

    const { result } = renderHook(
      () =>
        useRevokeSession({
          onCurrentSessionRevoked,
        }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    await expect(
      result.current.mutateAsync({
        sessionId: currentSession.id,
        current: true,
      }),
    ).rejects.toMatchObject({
      errorClass: "server",
      code: "INTERNAL_ERROR",
      message: "Erreur serveur",
    });

    expect(onCurrentSessionRevoked).not.toHaveBeenCalled();
    expect(invalidateQueries).not.toHaveBeenCalled();
  });
});
