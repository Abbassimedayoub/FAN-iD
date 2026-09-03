import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { AdminOrganizerCommissionSection } from "./AdminOrganizerCommissionSection";
import type { Organizer } from "./types";

const originalAdapter = httpClient.defaults.adapter;
const ORGANIZER_ID = "00000000-0000-4000-8000-000000000001";
const CHALLENGE_ID = "00000000-0000-4000-8000-000000000099";

const organizer: Organizer = {
  id: ORGANIZER_ID,
  org_name: "Association Lumière",
  validation_status: "PENDING",
  commission_rate: "0.0000",
  vat_number: null,
  contact_email: "contact@example.test",
  rejection_reason: null,
  validated_at: null,
  version: 4,
  created_at: "2026-09-03T14:00:00Z",
  updated_at: "2026-09-03T15:00:00Z",
};

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
    statusText: String(status),
  };
}

function apiError(
  config: InternalAxiosRequestConfig,
  status: number,
  code: string,
  message: string,
): AxiosError {
  const axiosResponse = response(config, status, {
    error: {
      code,
      message,
      details: {},
    },
  });

  return new AxiosError(
    `Request failed with status code ${status}`,
    "ERR_BAD_REQUEST",
    config,
    undefined,
    axiosResponse,
  );
}

function negotiating() {
  return {
    organizer_id: ORGANIZER_ID,
    validation_status: "PENDING",
    commission_status: "NEGOTIATING",
    agreed_rate: null,
    agreed_at: null,
    version: 4,
    proposals: [
      {
        id: "00000000-0000-4000-8000-000000000010",
        sequence: 1,
        proposer_role: "ORGANIZER",
        proposed_by_id: "00000000-0000-4000-8000-000000000020",
        rate: "0.1200",
        created_at: "2026-09-03T14:05:00Z",
        accepted_at: null,
        accepted_by_id: null,
      },
    ],
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("charge la négociation à la demande et protège l acceptation Admin par step-up", async () => {
  let negotiationGets = 0;
  let acceptCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (
      config.method === "get" &&
      config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/commission-negotiation`
    ) {
      negotiationGets += 1;
      return response(config, 200, negotiating());
    }

    if (
      config.method === "post" &&
      config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/commission-accept`
    ) {
      acceptCalls += 1;
      expect(config.headers.get("If-Match")).toBe('"4"');

      if (acceptCalls === 1) {
        throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
      }

      return response(config, 200, {
        ...negotiating(),
        validation_status: "APPROVED",
        commission_status: "COMMISSION_AGREED",
        agreed_rate: "0.1200",
        agreed_at: "2026-09-03T16:00:00Z",
        version: 5,
        proposals: [
          {
            ...negotiating().proposals[0],
            accepted_at: "2026-09-03T16:00:00Z",
            accepted_by_id: "00000000-0000-4000-8000-000000000030",
          },
        ],
      });
    }

    if (config.method === "post" && config.url === "/api/v1/auth/step-up/request") {
      return response(config, 200, {
        challenge_id: CHALLENGE_ID,
        expires_in_seconds: 300,
      });
    }

    if (config.method === "post" && config.url === "/api/v1/auth/step-up/confirm") {
      expect(config.data).toBe(
        JSON.stringify({
          challenge_id: CHALLENGE_ID,
          code: "123456",
        }),
      );

      return response(config, 204, undefined);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <AdminOrganizerCommissionSection organizer={organizer} />
    </QueryClientProvider>,
  );

  expect(negotiationGets).toBe(0);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Gérer la commission",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Négociation de commission",
    }),
  ).toBeInTheDocument();

  expect(screen.getByText("12 %")).toBeInTheDocument();
  expect(negotiationGets).toBe(1);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Accepter 12 %",
    }),
  );

  expect(
    await screen.findByRole("heading", {
      name: "Vérification renforcée",
    }),
  ).toBeInTheDocument();

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

  expect(await screen.findByText("Commission acceptée : 12 %. Compte organisateur approuvé automatiquement.")).toBeInTheDocument();
  expect(acceptCalls).toBe(2);

  queryClient.clear();
});
