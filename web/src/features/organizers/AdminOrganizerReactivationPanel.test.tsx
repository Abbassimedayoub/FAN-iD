import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { AdminOrganizerReactivationPanel } from "./AdminOrganizerReactivationPanel";
import type { Organizer } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const ORGANIZER_ID = "00000000-0000-4000-8000-000000000001";

const organizer: Organizer = {
  id: ORGANIZER_ID,
  org_name: "Club Africain",
  validation_status: "SUSPENDED",
  commission_rate: "0.0000",
  vat_number: null,
  contact_email: "club@example.test",
  rejection_reason: null,
  validated_at: "2026-08-20T10:00:00Z",
  version: 5,
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-30T10:00:00Z",
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

function apiError(
  config: InternalAxiosRequestConfig,
  status: number,
  code: string,
  message: string,
): AxiosError {
  return new AxiosError(
    message,
    "ERR_BAD_REQUEST",
    config,
    undefined,
    response(config, status, {
      error: {
        code,
        message,
        details: {},
      },
    }),
  );
}

function reactivationRequest(status: "PENDING" | "APPROVED" | "REJECTED") {
  return {
    id: "00000000-0000-4000-8000-000000000050",
    organizer_id: ORGANIZER_ID,
    requested_by_id: "00000000-0000-4000-8000-000000000051",
    organizer_version: 5,
    status,
    reviewed_by_id: status === "PENDING" ? null : "00000000-0000-4000-8000-000000000052",
    reviewed_at: status === "PENDING" ? null : "2026-08-30T16:30:00Z",
    rejection_reason: null,
    created_at: "2026-08-30T16:00:00Z",
    updated_at: "2026-08-30T16:00:00Z",
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("fait approuver une réouverture uniquement après le step-up OTP administrateur", async () => {
  const challengeId = "00000000-0000-4000-8000-000000000099";

  const calls: string[] = [];
  let approveCalls = 0;
  let currentStatus: "PENDING" | "APPROVED" | "REJECTED" = "PENDING";

  const adapter: AxiosAdapter = async (config) => {
    const call = `${String(config.method).toUpperCase()} ${config.url ?? ""}`;
    calls.push(call);

    if (
      config.method === "get" &&
      config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/reactivation-request`
    ) {
      return response(config, 200, {
        request: reactivationRequest(currentStatus),
      });
    }

    if (
      config.method === "post" &&
      config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/reactivation-request/approve`
    ) {
      approveCalls += 1;

      expect(config.headers.get("If-Match")).toBe('"5"');

      if (approveCalls === 1) {
        throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
      }

      currentStatus = "APPROVED";

      return response(config, 200, {
        request: reactivationRequest("APPROVED"),
        organizer: {
          id: ORGANIZER_ID,
          validation_status: "APPROVED",
          version: 6,
        },
      });
    }

    if (config.method === "post" && config.url === "/api/v1/auth/step-up/request") {
      return response(config, 200, {
        challenge_id: challengeId,
        expires_in_seconds: 300,
      });
    }

    if (config.method === "post" && config.url === "/api/v1/auth/step-up/confirm") {
      expect(config.data).toBe(
        JSON.stringify({
          challenge_id: challengeId,
          code: "123456",
        }),
      );

      return response(config, 204, undefined);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  httpClient.defaults.adapter = adapter;

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <AdminOrganizerReactivationPanel organizer={organizer} />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Statut de la demande : En attente")).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Approuver la réouverture",
    }),
  );

  expect(
    screen.getByRole("dialog", {
      name: "Approuver la réouverture",
    }),
  ).toBeInTheDocument();

  expect(screen.getByText(/Le code expire après 5 minutes/)).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Confirmer la réouverture",
    }),
  );

  expect(
    await screen.findByRole("dialog", {
      name: "Vérification renforcée",
    }),
  ).toBeInTheDocument();

  expect(screen.getByText("Le code expire dans 300 secondes.")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Code de vérification"), {
    target: {
      value: "123456",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Confirmer le code",
    }),
  );

  expect(await screen.findByText("Réouverture approuvée.")).toBeInTheDocument();

  expect(approveCalls).toBe(2);

  expect(calls).toContain(
    `POST /api/v1/admin/organizers/${ORGANIZER_ID}/reactivation-request/approve`,
  );
  expect(calls).toContain("POST /api/v1/auth/step-up/request");
  expect(calls).toContain("POST /api/v1/auth/step-up/confirm");

  queryClient.clear();
});
