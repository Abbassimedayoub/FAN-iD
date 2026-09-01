import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from "axios";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StepUpDialog } from "@/features/auth/StepUpDialog";
import { httpClient } from "@/lib/httpClient";

import { AdminOrganizerDetailPage } from "./AdminOrganizerDetailPage";
import { AdminOrganizerDetailView } from "./AdminOrganizerDetailView";
import { ApproveDialog, RejectDialog } from "./OrganizerActionDialogs";
import type { Organizer, OrganizerStatus } from "./types";

const originalAdapter = httpClient.defaults.adapter;
vi.mock("./AdminOrganizerEventsPanel", () => ({
  AdminOrganizerEventsPanel: () => null,
}));

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

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/admin/organizers/${ORGANIZER_ID}`]}>
      <QueryClientProvider client={createQueryClient()}>
        <Routes>
          <Route path="/admin/organizers/:organizerId" element={<AdminOrganizerDetailPage />} />
        </Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
  vi.restoreAllMocks();
});

describe("OrganizerActionDialogs", () => {
  it("conserve le motif de rejet lorsque la mutation échoue", async () => {
    const onConfirm = vi.fn(async () => false);

    render(<RejectDialog open isPending={false} onClose={vi.fn()} onConfirm={onConfirm} />);

    const textarea = screen.getByLabelText("Motif du rejet");

    fireEvent.change(textarea, {
      target: {
        value: "  Dossier incomplet  ",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le rejet" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith("Dossier incomplet");
    });

    expect(screen.getByRole("dialog", { name: "Rejeter la demande" })).toBeInTheDocument();
    expect(textarea).toHaveValue("  Dossier incomplet  ");
  });

  it("bloque un double submit dès la première confirmation", async () => {
    let resolveConfirmation: ((value: boolean) => void) | undefined;

    const onConfirm = vi.fn(
      () =>
        new Promise<boolean>((resolve) => {
          resolveConfirmation = resolve;
        }),
    );

    render(<ApproveDialog open isPending={false} onClose={vi.fn()} onConfirm={onConfirm} />);

    const confirmButton = screen.getByRole("button", {
      name: "Confirmer l’approbation",
    });

    fireEvent.click(confirmButton);

    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Traitement…" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Traitement…" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveConfirmation?.(false);
    });
  });
  it("ferme une confirmation depuis le bouton Fermer lorsqu’elle est disponible", () => {
    const onClose = vi.fn();

    render(
      <ApproveDialog
        open
        isPending={false}
        onClose={onClose}
        onConfirm={vi.fn(async () => false)}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("ferme le dialogue de rejet après une confirmation réussie", async () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn(async () => true);

    render(<RejectDialog open isPending={false} onClose={onClose} onConfirm={onConfirm} />);

    fireEvent.change(screen.getByLabelText("Motif du rejet"), {
      target: {
        value: "Dossier incomplet",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le rejet" }));

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith("Dossier incomplet");
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});

describe("AdminOrganizerDetailPage actions", () => {
  it("ferme le dialogue de rejet depuis la fiche", () => {
    render(
      <AdminOrganizerDetailView
        data={organizer}
        isPending={false}
        isFetching={false}
        error={null}
        onRetry={vi.fn()}
        onBack={vi.fn()}
        actions={{
          isPending: false,
          feedback: null,
          isStaleResource: false,
          onApprove: vi.fn(async () => true),
          onReject: vi.fn(async () => true),
          onSuspend: vi.fn(async () => true),
          onReloadStale: vi.fn(),
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Rejeter" }));

    expect(
      screen.getByRole("dialog", {
        name: "Rejeter la demande",
      }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));

    expect(
      screen.queryByRole("dialog", {
        name: "Rejeter la demande",
      }),
    ).not.toBeInTheDocument();
  });

  it("approuve une demande pending et affiche le succès", async () => {
    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "post") {
        return response(config, 200, {
          ...organizer,
          validation_status: "APPROVED",
          version: 5,
        });
      }

      return response(config, 200, organizer);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’approbation" }));

    expect(await screen.findByText("Demande approuvée.")).toBeInTheDocument();
    expect(screen.getByText("Approuvé")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suspendre" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Approuver la demande" })).not.toBeInTheDocument();
  });

  it("conserve le formulaire de rejet et affiche un toast lorsque la mutation échoue", async () => {
    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "post") {
        throw apiError(config, 500, "INTERNAL_ERROR", "Échec du rejet");
      }

      return response(config, 200, organizer);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Rejeter" }));

    const textarea = screen.getByLabelText("Motif du rejet");

    fireEvent.change(textarea, {
      target: {
        value: "Pièce justificative manquante",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le rejet" }));

    expect(await screen.findByText("Échec du rejet")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Rejeter la demande" })).toBeInTheDocument();
    expect(textarea).toHaveValue("Pièce justificative manquante");
  });

  it("traite STALE_RESOURCE par un dialogue puis recharge la fiche", async () => {
    let getCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "post") {
        throw apiError(config, 409, "STALE_RESOURCE", "Version obsolète");
      }

      getCalls += 1;

      if (getCalls === 1) {
        return response(config, 200, organizer);
      }

      return response(config, 200, {
        ...organizer,
        validation_status: "APPROVED",
        version: 5,
      });
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’approbation" }));

    expect(
      await screen.findByRole("dialog", {
        name: "Le dossier a changé",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("dialog", {
        name: "Approuver la demande",
      }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Recharger le dossier" }));

    expect(await screen.findByText("Approuvé")).toBeInTheDocument();
    expect(getCalls).toBe(2);
  });

  it("suspend un organisateur approuvé", async () => {
    const approved: Organizer = {
      ...organizer,
      validation_status: "APPROVED",
      version: 7,
    };

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "post") {
        return response(config, 200, {
          ...approved,
          validation_status: "SUSPENDED",
          version: 8,
        });
      }

      return response(config, 200, approved);
    };

    httpClient.defaults.adapter = adapter;

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Suspendre" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer la suspension" }));

    expect(await screen.findByText("Organisateur suspendu.")).toBeInTheDocument();
    expect(screen.getByText("Suspendu")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suspendre" })).not.toBeInTheDocument();
  });

  it.each<OrganizerStatus>(["REJECTED", "SUSPENDED"])(
    "ne propose aucune action administrative pour %s",
    (validationStatus) => {
      render(
        <AdminOrganizerDetailView
          data={{
            ...organizer,
            validation_status: validationStatus,
          }}
          isPending={false}
          isFetching={false}
          error={null}
          onRetry={vi.fn()}
          onBack={vi.fn()}
          actions={{
            isPending: false,
            feedback: null,
            isStaleResource: false,
            onApprove: vi.fn(async () => true),
            onReject: vi.fn(async () => true),
            onSuspend: vi.fn(async () => true),
            onReloadStale: vi.fn(),
          }}
        />,
      );

      expect(
        screen.queryByRole("heading", {
          name: "Actions administratives",
        }),
      ).not.toBeInTheDocument();
    },
  );
});

describe("AdminOrganizerDetailPage step-up", () => {
  it("demande le step-up, confirme le code puis rejoue l’approbation", async () => {
    const challengeId = "00000000-0000-4000-8000-000000000099";
    const postUrls: string[] = [];
    let approveCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      postUrls.push(config.url ?? "");

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`) {
        approveCalls += 1;
        expect(config.headers.get("If-Match")).toBe('"4"');

        if (approveCalls === 1) {
          throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
        }

        return response(config, 200, {
          ...organizer,
          validation_status: "APPROVED",
          version: 5,
        });
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        expect(config.data).toBe(JSON.stringify({}));

        return response(config, 200, {
          challenge_id: challengeId,
          expires_in_seconds: 300,
        });
      }

      if (config.url === "/api/v1/auth/step-up/confirm") {
        expect(config.data).toBe(
          JSON.stringify({
            challenge_id: challengeId,
            code: "ABC-123",
          }),
        );

        return response(config, 204, undefined);
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’approbation" }));

    expect(
      await screen.findByRole("dialog", { name: "Vérification renforcée" }),
    ).toBeInTheDocument();

    expect(screen.queryByRole("dialog", { name: "Approuver la demande" })).not.toBeInTheDocument();

    const codeInput = screen.getByLabelText("Code de vérification");

    expect(codeInput).toHaveAttribute("maxlength", "16");
    expect(codeInput).not.toHaveAttribute("pattern");

    fireEvent.change(codeInput, {
      target: {
        value: "  ABC-123  ",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le code" }));

    expect(await screen.findByText("Demande approuvée.")).toBeInTheDocument();
    expect(approveCalls).toBe(2);

    expect(postUrls).toEqual([
      `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`,
      "/api/v1/auth/step-up/request",
      "/api/v1/auth/step-up/confirm",
      `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`,
    ]);
  });

  it("rouvre le rejet avec le même motif si le retry métier échoue après le step-up", async () => {
    const challengeId = "00000000-0000-4000-8000-000000000098";
    const rejectPayloads: string[] = [];
    let rejectCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/reject`) {
        rejectCalls += 1;
        rejectPayloads.push(String(config.data));

        if (rejectCalls === 1) {
          throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
        }

        throw apiError(config, 500, "INTERNAL_ERROR", "Échec du rejet");
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        return response(config, 200, {
          challenge_id: challengeId,
          expires_in_seconds: 300,
        });
      }

      if (config.url === "/api/v1/auth/step-up/confirm") {
        return response(config, 204, undefined);
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Rejeter" }));

    fireEvent.change(screen.getByLabelText("Motif du rejet"), {
      target: {
        value: "  Pièce justificative manquante  ",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le rejet" }));

    expect(
      await screen.findByRole("dialog", { name: "Vérification renforcée" }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Code de vérification"), {
      target: {
        value: "ABC-123",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le code" }));

    expect(await screen.findByText("Échec du rejet")).toBeInTheDocument();

    expect(await screen.findByRole("dialog", { name: "Rejeter la demande" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByLabelText("Motif du rejet")).toHaveValue("Pièce justificative manquante");
    });

    expect(rejectPayloads).toEqual([
      JSON.stringify({
        reason: "Pièce justificative manquante",
      }),
      JSON.stringify({
        reason: "Pièce justificative manquante",
      }),
    ]);

    expect(
      screen.queryByRole("dialog", { name: "Vérification renforcée" }),
    ).not.toBeInTheDocument();
  });

  it("conserve le code et le dialogue lorsque la confirmation renvoie OTP_INVALID", async () => {
    const challengeId = "00000000-0000-4000-8000-000000000097";
    let approveCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`) {
        approveCalls += 1;

        throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        return response(config, 200, {
          challenge_id: challengeId,
          expires_in_seconds: 300,
        });
      }

      if (config.url === "/api/v1/auth/step-up/confirm") {
        throw apiError(config, 400, "OTP_INVALID", "Code de vérification invalide");
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’approbation" }));

    const codeInput = await screen.findByLabelText("Code de vérification");

    fireEvent.change(codeInput, {
      target: {
        value: "ABC-123",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le code" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Code de vérification invalide");

    expect(screen.getByRole("dialog", { name: "Vérification renforcée" })).toBeInTheDocument();

    expect(codeInput).toHaveValue("ABC-123");
    expect(approveCalls).toBe(1);
  });

  it("préserve le formulaire de rejet si la création du challenge échoue", async () => {
    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/reject`) {
        throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        throw apiError(config, 429, "THROTTLED", "Trop de tentatives");
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Rejeter" }));

    const textarea = screen.getByLabelText("Motif du rejet");

    fireEvent.change(textarea, {
      target: {
        value: "Document expiré",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le rejet" }));

    expect(await screen.findByText("Trop de tentatives")).toBeInTheDocument();

    expect(screen.getByRole("dialog", { name: "Rejeter la demande" })).toBeInTheDocument();

    expect(textarea).toHaveValue("Document expiré");

    expect(
      screen.queryByRole("dialog", { name: "Vérification renforcée" }),
    ).not.toBeInTheDocument();
  });

  it("bloque un double submit pendant la confirmation du step-up", async () => {
    const challengeId = "00000000-0000-4000-8000-000000000096";
    let approveCalls = 0;
    let confirmCalls = 0;
    let releaseConfirm: (() => void) | undefined;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`) {
        approveCalls += 1;

        if (approveCalls === 1) {
          throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
        }

        return response(config, 200, {
          ...organizer,
          validation_status: "APPROVED",
          version: 5,
        });
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        return response(config, 200, {
          challenge_id: challengeId,
          expires_in_seconds: 300,
        });
      }

      if (config.url === "/api/v1/auth/step-up/confirm") {
        confirmCalls += 1;

        await new Promise<void>((resolve) => {
          releaseConfirm = resolve;
        });

        return response(config, 204, undefined);
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’approbation" }));

    fireEvent.change(await screen.findByLabelText("Code de vérification"), {
      target: {
        value: "123456",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le code" }));

    await waitFor(() => {
      expect(confirmCalls).toBe(1);
    });

    const busyButton = screen.getByRole("button", {
      name: "Vérification…",
    });

    expect(busyButton).toBeDisabled();

    fireEvent.click(busyButton);
    expect(confirmCalls).toBe(1);

    await act(async () => {
      releaseConfirm?.();
    });

    expect(await screen.findByText("Demande approuvée.")).toBeInTheDocument();
    expect(confirmCalls).toBe(1);
    expect(approveCalls).toBe(2);
  });

  it("conserve STALE_RESOURCE lorsque le retry après step-up est obsolète", async () => {
    const challengeId = "00000000-0000-4000-8000-000000000095";
    let approveCalls = 0;
    let getCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        getCalls += 1;

        if (getCalls === 1) {
          return response(config, 200, organizer);
        }

        return response(config, 200, {
          ...organizer,
          version: 5,
        });
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`) {
        approveCalls += 1;

        if (approveCalls === 1) {
          throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
        }

        throw apiError(config, 409, "STALE_RESOURCE", "Version obsolète");
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        return response(config, 200, {
          challenge_id: challengeId,
          expires_in_seconds: 300,
        });
      }

      if (config.url === "/api/v1/auth/step-up/confirm") {
        return response(config, 204, undefined);
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Approuver" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmer l’approbation" }));

    fireEvent.change(await screen.findByLabelText("Code de vérification"), {
      target: {
        value: "123456",
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirmer le code" }));

    expect(await screen.findByRole("dialog", { name: "Le dossier a changé" })).toBeInTheDocument();

    expect(
      screen.queryByRole("dialog", { name: "Vérification renforcée" }),
    ).not.toBeInTheDocument();

    expect(approveCalls).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: "Recharger le dossier" }));

    await waitFor(() => {
      expect(getCalls).toBe(2);
    });
  });
});

describe("complément de couverture step-up", () => {
  it("réinitialise le code lorsque le dialogue est fermé puis accepte Fermer", () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn(async () => false);

    const { rerender } = render(
      <StepUpDialog
        open
        expiresInSeconds={300}
        error={null}
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.change(screen.getByLabelText("Code de vérification"), {
      target: {
        value: "ABC-123",
      },
    });

    expect(screen.getByLabelText("Code de vérification")).toHaveValue("ABC-123");

    rerender(
      <StepUpDialog
        open={false}
        expiresInSeconds={300}
        error={null}
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    );

    rerender(
      <StepUpDialog
        open
        expiresInSeconds={300}
        error={null}
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByLabelText("Code de vérification")).toHaveValue("");

    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("rouvre l’approbation si le retry métier échoue après un step-up valide", async () => {
    const challengeId = "00000000-0000-4000-8000-000000000094";
    let approveCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/approve`) {
        approveCalls += 1;

        if (approveCalls === 1) {
          throw apiError(config, 403, "STEP_UP_REQUIRED", "Une vérification renforcée est requise");
        }

        throw apiError(config, 500, "INTERNAL_ERROR", "Échec de l’approbation");
      }

      if (config.url === "/api/v1/auth/step-up/request") {
        return response(config, 200, {
          challenge_id: challengeId,
          expires_in_seconds: 300,
        });
      }

      if (config.url === "/api/v1/auth/step-up/confirm") {
        return response(config, 204, undefined);
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Approuver",
      }),
    );

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirmer l’approbation",
      }),
    );

    fireEvent.change(await screen.findByLabelText("Code de vérification"), {
      target: {
        value: "123456",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirmer le code",
      }),
    );

    expect(await screen.findByText("Échec de l’approbation")).toBeInTheDocument();

    expect(
      await screen.findByRole("dialog", {
        name: "Approuver la demande",
      }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("dialog", {
        name: "Vérification renforcée",
      }),
    ).not.toBeInTheDocument();

    expect(approveCalls).toBe(2);
  });

  it("exécute jusqu’au bout un rejet réussi", async () => {
    let rejectCalls = 0;

    const adapter: AxiosAdapter = async (config) => {
      if (config.method === "get") {
        return response(config, 200, organizer);
      }

      if (config.url === `/api/v1/admin/organizers/${ORGANIZER_ID}/reject`) {
        rejectCalls += 1;

        expect(config.headers.get("If-Match")).toBe('"4"');
        expect(config.data).toBe(
          JSON.stringify({
            reason: "Dossier non conforme",
          }),
        );

        return response(config, 200, {
          ...organizer,
          validation_status: "REJECTED",
          rejection_reason: "Dossier non conforme",
          version: 5,
        });
      }

      throw new Error(`URL inattendue : ${config.url ?? "<vide>"}`);
    };

    httpClient.defaults.adapter = adapter;
    renderPage();

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Rejeter",
      }),
    );

    fireEvent.change(screen.getByLabelText("Motif du rejet"), {
      target: {
        value: "  Dossier non conforme  ",
      },
    });

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirmer le rejet",
      }),
    );

    expect(await screen.findByText("Demande rejetée.")).toBeInTheDocument();

    expect(rejectCalls).toBe(1);

    expect(
      screen.queryByRole("dialog", {
        name: "Rejeter la demande",
      }),
    ).not.toBeInTheDocument();
  });
});
