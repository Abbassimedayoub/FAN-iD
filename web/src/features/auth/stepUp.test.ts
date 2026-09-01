import { type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { clearAccessToken, getAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import { confirmStepUp, requestStepUp } from "./stepUp";

const originalAdapter = httpClient.defaults.adapter;

const CHALLENGE_ID = "00000000-0000-4000-8000-000000000002";

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

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  clearAccessToken();
});

describe("step-up transport", () => {
  it("demande un challenge authentifié avec le corps vide exact", async () => {
    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("post");
      expect(config.url).toBe("/api/v1/auth/step-up/request");
      expect(config.data).toBe(JSON.stringify({}));
      expect(config.headers.get("Authorization")).toBe("Bearer access-token");

      return response(config, 200, {
        challenge_id: CHALLENGE_ID,
        expires_in_seconds: 300,
      });
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("access-token");

    const result = await requestStepUp();

    expect(result).toEqual({
      challenge_id: CHALLENGE_ID,
      expires_in_seconds: 300,
    });
    expect(getAccessToken()).toBe("access-token");
  });

  it("confirme le challenge avec le payload exact sans remplacer le bearer", async () => {
    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("post");
      expect(config.url).toBe("/api/v1/auth/step-up/confirm");
      expect(config.data).toBe(
        JSON.stringify({
          challenge_id: CHALLENGE_ID,
          code: "123456",
        }),
      );
      expect(config.headers.get("Authorization")).toBe("Bearer access-token");

      return response(config, 204, undefined);
    };

    httpClient.defaults.adapter = adapter;
    setAccessToken("access-token");

    await expect(confirmStepUp(CHALLENGE_ID, "123456")).resolves.toBeUndefined();

    expect(getAccessToken()).toBe("access-token");
  });
});
