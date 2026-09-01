import { type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { approveOrganizer, rejectOrganizer, suspendOrganizer } from "./api";
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
});

describe("organizer admin mutation transport", () => {
  it("approuve sans body avec le If-Match exact", async () => {
    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("post");
      expect(config.url).toBe(`/api/v1/admin/organizers/${ORGANIZER_ID}/approve`);
      expect(config.data).toBeUndefined();
      expect(config.headers.get("If-Match")).toBe('"4"');

      return response(config, 200, {
        ...organizer,
        validation_status: "APPROVED",
        version: 5,
      });
    };

    httpClient.defaults.adapter = adapter;

    const result = await approveOrganizer(ORGANIZER_ID, 4);

    expect(result.validation_status).toBe("APPROVED");
    expect(result.version).toBe(5);
  });

  it("rejette avec le reason exact et le If-Match exact", async () => {
    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("post");
      expect(config.url).toBe(`/api/v1/admin/organizers/${ORGANIZER_ID}/reject`);
      expect(config.data).toBe(JSON.stringify({ reason: "Dossier incomplet" }));
      expect(config.headers.get("If-Match")).toBe('"4"');

      return response(config, 200, {
        ...organizer,
        validation_status: "REJECTED",
        rejection_reason: "Dossier incomplet",
        version: 5,
      });
    };

    httpClient.defaults.adapter = adapter;

    const result = await rejectOrganizer(ORGANIZER_ID, 4, "Dossier incomplet");

    expect(result.validation_status).toBe("REJECTED");
    expect(result.rejection_reason).toBe("Dossier incomplet");
    expect(result.version).toBe(5);
  });

  it("suspend sans body avec le If-Match exact", async () => {
    const adapter: AxiosAdapter = async (config) => {
      expect(config.method).toBe("post");
      expect(config.url).toBe(`/api/v1/admin/organizers/${ORGANIZER_ID}/suspend`);
      expect(config.data).toBeUndefined();
      expect(config.headers.get("If-Match")).toBe('"7"');

      return response(config, 200, {
        ...organizer,
        validation_status: "SUSPENDED",
        version: 8,
      });
    };

    httpClient.defaults.adapter = adapter;

    const result = await suspendOrganizer(ORGANIZER_ID, 7);

    expect(result.validation_status).toBe("SUSPENDED");
    expect(result.version).toBe(8);
  });
});
