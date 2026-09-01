import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import { httpClient } from "@/lib/httpClient";

import { OrganizerScannersPage } from "./OrganizerScannersPage";
import type { OrganizerScanner } from "./scanners";
import type { Organizer } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const CHALLENGE_REVOKE = "00000000-0000-4000-8000-000000000101";
const CHALLENGE_LEAVE = "00000000-0000-4000-8000-000000000102";

const organizerUser = {
  id: "user-organizer-1",
  email: "organizer@example.test",
  first_name: "Ines",
  last_name: "Bouzid",
  role: "ORGANIZER" as const,
  created_at: "2026-08-25T15:00:00Z",
};

const approvedOrganizer: Organizer = {
  id: "00000000-0000-4000-8000-000000000001",
  org_name: "Association Lumière",
  validation_status: "APPROVED",
  commission_rate: "0.1000",
  vat_number: null,
  contact_email: "organizer@example.test",
  rejection_reason: null,
  validated_at: "2026-08-20T10:00:00Z",
  version: 4,
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-20T10:00:00Z",
};

const activeScanner: OrganizerScanner = {
  id: "00000000-0000-4000-8000-000000000011",
  user_id: "00000000-0000-4000-8000-000000000021",
  first_name: "Nadia",
  last_name: "Active",
  email: "nadia@example.test",
  phone: null,
  status: "ACTIVE",
  scanner_email_sent_at: "2026-08-27T10:00:00Z",
  organizer_email_sent_at: "2026-08-27T10:00:00Z",
  opened_at: "2026-08-27T11:00:00Z",
  activated_at: "2026-08-27T12:00:00Z",
  removed_at: null,
  archived_at: null,
  password_help_pending: false,
  password_help_requested_at: null,
  created_at: "2026-08-27T09:00:00Z",
  updated_at: "2026-08-27T12:00:00Z",
  version: 7,
};

const leaveScanner: OrganizerScanner = {
  ...activeScanner,
  id: "00000000-0000-4000-8000-000000000012",
  user_id: "00000000-0000-4000-8000-000000000022",
  first_name: "Lina",
  last_name: "Leave",
  email: "lina@example.test",
  status: "LEAVE_REQUESTED",
  version: 9,
};

interface CapturedCall {
  method: string;
  url: string;
  body: Record<string, unknown>;
  ifMatch: string | null;
}

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
    statusText: status === 204 ? "No Content" : "OK",
  };
}

function apiError(
  config: InternalAxiosRequestConfig,
  status: number,
  code: string,
  message: string,
): AxiosError {
  return new AxiosError(
    `Request failed with status code ${status}`,
    status >= 500 ? "ERR_BAD_RESPONSE" : "ERR_BAD_REQUEST",
    config,
    undefined,
    response(config, status, {
      error: {
        code,
        message,
        details: {},
        correlation_id: `corr-${status}`,
      },
    }),
  );
}

function requestBody(config: InternalAxiosRequestConfig): Record<string, unknown> {
  if (typeof config.data === "string") {
    return JSON.parse(config.data) as Record<string, unknown>;
  }

  if (config.data && typeof config.data === "object") {
    return config.data as Record<string, unknown>;
  }

  return {};
}

function capture(config: InternalAxiosRequestConfig): CapturedCall {
  const header = config.headers?.get("If-Match");

  return {
    method: config.method ?? "",
    url: config.url ?? "",
    body: requestBody(config),
    ifMatch: header == null ? null : String(header),
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

function installAdapter(
  scanners: OrganizerScanner[],
  action: (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>,
): void {
  const adapter: AxiosAdapter = async (config) => {
    if (config.method === "get" && config.url === "/api/v1/organizers/me") {
      return response(config, 200, approvedOrganizer);
    }

    if (config.method === "get" && config.url === "/api/v1/organizers/me/scanners") {
      return response(config, 200, scanners);
    }

    return action(config);
  };

  httpClient.defaults.adapter = adapter;
}

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider initialUser={organizerUser}>
        <MemoryRouter initialEntries={["/organizer/scanners"]}>
          <OrganizerScannersPage />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
});

describe("OrganizerScannersPage - OTP actions sensibles", () => {
  it("demande REVOKE puis retire le scanner avec le challenge et le code", async () => {
    const calls: CapturedCall[] = [];

    installAdapter([activeScanner], async (config) => {
      if (
        config.method === "post" &&
        config.url === `/api/v1/organizers/me/scanners/${activeScanner.id}/security-code`
      ) {
        calls.push(capture(config));

        return response(config, 200, {
          challenge_id: CHALLENGE_REVOKE,
          expires_in_seconds: 300,
        });
      }

      if (
        config.method === "delete" &&
        config.url === `/api/v1/organizers/me/scanners/${activeScanner.id}`
      ) {
        calls.push(capture(config));
        return response(config, 204, undefined);
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    });

    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Retirer le scanner",
      }),
    );

    expect(
      await screen.findByRole("dialog", {
        name: "Retirer le scanner",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Recevoir le code et continuer",
      }),
    );

    expect(
      await screen.findByRole("dialog", {
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

    expect(await screen.findByText("Scanner retiré.")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", {
          name: "Vérification renforcée",
        }),
      ).not.toBeInTheDocument();
    });

    expect(calls).toEqual([
      {
        method: "post",
        url: `/api/v1/organizers/me/scanners/${activeScanner.id}/security-code`,
        body: {
          action: "REVOKE",
        },
        ifMatch: null,
      },
      {
        method: "delete",
        url: `/api/v1/organizers/me/scanners/${activeScanner.id}`,
        body: {
          challenge_id: CHALLENGE_REVOKE,
          code: "123456",
        },
        ifMatch: '"7"',
      },
    ]);
  });

  it("demande LEAVE_ACCEPT puis accepte le départ avec OTP", async () => {
    const calls: CapturedCall[] = [];

    installAdapter([leaveScanner], async (config) => {
      if (
        config.method === "post" &&
        config.url === `/api/v1/organizers/me/scanners/${leaveScanner.id}/security-code`
      ) {
        calls.push(capture(config));

        return response(config, 200, {
          challenge_id: CHALLENGE_LEAVE,
          expires_in_seconds: 300,
        });
      }

      if (
        config.method === "post" &&
        config.url === `/api/v1/organizers/me/scanners/${leaveScanner.id}/leave-request`
      ) {
        calls.push(capture(config));
        return response(config, 204, undefined);
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    });

    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Accepter",
      }),
    );

    expect(
      await screen.findByRole("dialog", {
        name: "Accepter la demande de départ",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Recevoir le code et continuer",
      }),
    );

    expect(
      await screen.findByRole("dialog", {
        name: "Vérification renforcée",
      }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Code de vérification"), {
      target: {
        value: "654321",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirmer le code",
      }),
    );

    expect(
      await screen.findByText(
        "Demande acceptée. Le scanner a été retiré et ses sessions ont été révoquées.",
      ),
    ).toBeInTheDocument();

    expect(calls).toEqual([
      {
        method: "post",
        url: `/api/v1/organizers/me/scanners/${leaveScanner.id}/security-code`,
        body: {
          action: "LEAVE_ACCEPT",
        },
        ifMatch: null,
      },
      {
        method: "post",
        url: `/api/v1/organizers/me/scanners/${leaveScanner.id}/leave-request`,
        body: {
          decision: "ACCEPT",
          challenge_id: CHALLENGE_LEAVE,
          code: "654321",
        },
        ifMatch: '"9"',
      },
    ]);
  });

  it("refuse le départ directement sans créer de challenge OTP", async () => {
    const calls: CapturedCall[] = [];

    installAdapter([leaveScanner], async (config) => {
      if (
        config.method === "post" &&
        config.url === `/api/v1/organizers/me/scanners/${leaveScanner.id}/leave-request`
      ) {
        calls.push(capture(config));
        return response(config, 204, undefined);
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    });

    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Refuser",
      }),
    );

    expect(
      await screen.findByRole("dialog", {
        name: "Refuser la demande de départ",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Refuser la demande",
      }),
    );

    expect(await screen.findByText("Demande refusée. Le scanner reste actif.")).toBeInTheDocument();

    await waitFor(() => {
      expect(
        screen.queryByRole("dialog", {
          name: "Refuser la demande de départ",
        }),
      ).not.toBeInTheDocument();
    });

    expect(calls.some((call) => call.url.endsWith("/security-code"))).toBe(false);

    expect(calls).toEqual([
      {
        method: "post",
        url: `/api/v1/organizers/me/scanners/${leaveScanner.id}/leave-request`,
        body: {
          decision: "REJECT",
        },
        ifMatch: '"9"',
      },
    ]);
  });
  it("conserve la modale de retrait si la création du challenge échoue", async () => {
    let challengeCalls = 0;

    installAdapter([activeScanner], async (config) => {
      if (
        config.method === "post" &&
        config.url === `/api/v1/organizers/me/scanners/${activeScanner.id}/security-code`
      ) {
        challengeCalls += 1;

        throw apiError(config, 429, "THROTTLED", "Trop de tentatives");
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    });

    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Retirer le scanner",
      }),
    );

    expect(
      await screen.findByRole("dialog", {
        name: "Retirer le scanner",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Recevoir le code et continuer",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Trop de tentatives");

    expect(
      screen.getByRole("dialog", {
        name: "Retirer le scanner",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("dialog", {
        name: "Vérification renforcée",
      }),
    ).not.toBeInTheDocument();

    expect(challengeCalls).toBe(1);
  });

  it("conserve le Step-Up et le code lorsque le retrait renvoie OTP_INVALID", async () => {
    let deleteCalls = 0;

    installAdapter([activeScanner], async (config) => {
      if (
        config.method === "post" &&
        config.url === `/api/v1/organizers/me/scanners/${activeScanner.id}/security-code`
      ) {
        return response(config, 200, {
          challenge_id: CHALLENGE_REVOKE,
          expires_in_seconds: 300,
        });
      }

      if (
        config.method === "delete" &&
        config.url === `/api/v1/organizers/me/scanners/${activeScanner.id}`
      ) {
        deleteCalls += 1;

        expect(requestBody(config)).toEqual({
          challenge_id: CHALLENGE_REVOKE,
          code: "123456",
        });

        expect(config.headers?.get("If-Match")).toBe('"7"');

        throw apiError(config, 400, "OTP_INVALID", "Code de vérification invalide");
      }

      throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
    });

    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Retirer le scanner",
      }),
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Recevoir le code et continuer",
      }),
    );

    const codeInput = await screen.findByLabelText("Code de vérification");

    expect(
      screen.getByRole("dialog", {
        name: "Vérification renforcée",
      }),
    ).toBeInTheDocument();

    fireEvent.change(codeInput, {
      target: {
        value: "123456",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirmer le code",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Code de vérification invalide");

    expect(
      screen.getByRole("dialog", {
        name: "Vérification renforcée",
      }),
    ).toBeInTheDocument();

    expect(codeInput).toHaveValue("123456");
    expect(deleteCalls).toBe(1);
  });
});
