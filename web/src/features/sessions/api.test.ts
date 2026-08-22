import type { AxiosAdapter, AxiosResponse } from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { clearAccessToken, getAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import { listSessions, revokeSession } from "./api";
import type { AuthSession } from "./types";

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

describe("sessions transport", () => {
  afterEach(() => {
    clearAccessToken();
    httpClient.defaults.adapter = undefined;
  });

  it("liste les sessions via le contrat exact et conserve le bearer", async () => {
    const sessions: AuthSession[] = [
      {
        id: "00000000-0000-4000-8000-000000000001",
        device: {
          id: "00000000-0000-4000-8000-000000000010",
          label: "Téléphone personnel",
        },
        ip: "203.0.113.7",
        user_agent: "FAN-iD Web",
        issued_at: "2026-08-22T10:00:00Z",
        last_used_at: "2026-08-22T12:00:00Z",
        expires_at: "2026-09-21T10:00:00Z",
        current: true,
      },
      {
        id: "00000000-0000-4000-8000-000000000002",
        device: null,
        ip: null,
        user_agent: "",
        issued_at: "2026-08-21T10:00:00Z",
        last_used_at: "2026-08-21T11:00:00Z",
        expires_at: "2026-09-20T10:00:00Z",
        current: false,
      },
    ];

    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("get");
      expect(config.url).toBe("/api/v1/auth/sessions");
      expect(config.data).toBeUndefined();
      expect(config.headers.get("Authorization")).toBe("Bearer access-token");

      return response(config, 200, sessions);
    };

    setAccessToken("access-token");
    httpClient.defaults.adapter = adapter;

    await expect(listSessions()).resolves.toEqual(sessions);
    expect(getAccessToken()).toBe("access-token");
  });

  it("révoque une session par DELETE sans body et ne modifie pas le token", async () => {
    const sessionId = "00000000-0000-4000-8000-000000000002";

    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("delete");
      expect(config.url).toBe(`/api/v1/auth/sessions/${sessionId}`);
      expect(config.data).toBeUndefined();
      expect(config.headers.get("Authorization")).toBe("Bearer access-token");

      return response(config, 204, undefined);
    };

    setAccessToken("access-token");
    httpClient.defaults.adapter = adapter;

    await expect(revokeSession(sessionId)).resolves.toBeUndefined();
    expect(getAccessToken()).toBe("access-token");
  });
});
