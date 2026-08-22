import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AppError } from "@/lib/errors";

import { SessionsView } from "./SessionsView";
import type { AuthSession } from "./types";

const sessions: [AuthSession, AuthSession] = [
  {
    id: "00000000-0000-4000-8000-000000000001",
    device: {
      id: "10000000-0000-4000-8000-000000000001",
      label: "MacBook Pro",
    },
    ip: "203.0.113.7",
    user_agent: "Chrome sur macOS",
    issued_at: "2026-08-22T10:00:00Z",
    last_used_at: "2026-08-22T12:30:00Z",
    expires_at: "2026-09-21T10:00:00Z",
    current: true,
  },
  {
    id: "00000000-0000-4000-8000-000000000002",
    device: null,
    ip: null,
    user_agent: "",
    issued_at: "2026-08-20T08:00:00Z",
    last_used_at: "2026-08-21T09:15:00Z",
    expires_at: "2026-09-19T08:00:00Z",
    current: false,
  },
];

const networkError: AppError = {
  errorClass: "network",
  code: "NETWORK_ERROR",
  message: "Connexion indisponible",
  details: {},
  correlationId: "corr-sessions-1",
  traceId: null,
  httpStatus: null,
};

const serverError: AppError = {
  errorClass: "server",
  code: "INTERNAL_ERROR",
  message: "Erreur serveur",
  details: {},
  correlationId: "corr-sessions-500",
  traceId: null,
  httpStatus: 500,
};

const defaultProps = {
  sessions: undefined,
  isPending: false,
  isFetching: false,
  error: null,
  mutationPending: false,
  mutationError: null,
  onRetry: vi.fn(),
  onRevoke: vi.fn(),
};

describe("SessionsView - cinq états", () => {
  it("affiche cinq lignes skeleton au chargement initial", () => {
    render(<SessionsView {...defaultProps} isPending isFetching />);

    expect(
      screen.getByRole("table", {
        name: "Chargement des sessions",
      }),
    ).toBeInTheDocument();

    expect(screen.getAllByLabelText(/Chargement de la session/)).toHaveLength(5);
  });

  it("conserve les sessions pendant une actualisation", () => {
    render(<SessionsView {...defaultProps} sessions={sessions} isFetching />);

    expect(screen.getByText("Actualisation des sessions…")).toBeInTheDocument();

    expect(screen.getByText("MacBook Pro")).toBeInTheDocument();

    expect(screen.queryByLabelText("Chargement de la session 1")).not.toBeInTheDocument();
  });

  it("affiche l’état vide", () => {
    render(<SessionsView {...defaultProps} sessions={[]} />);

    expect(screen.getByText("Aucune session active")).toBeInTheDocument();
  });

  it("affiche l’erreur finale avec Réessayer sans données", () => {
    const onRetry = vi.fn();

    render(<SessionsView {...defaultProps} error={networkError} onRetry={onRetry} />);

    expect(screen.getByText("Connexion indisponible. Vérifiez votre réseau.")).toBeInTheDocument();

    expect(screen.getByText("Référence : corr-sessions-1")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Réessayer",
      }),
    );

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("affiche les sessions en succès et transmet la révocation", () => {
    const onRevoke = vi.fn();

    render(<SessionsView {...defaultProps} sessions={sessions} onRevoke={onRevoke} />);

    const table = screen.getByRole("table", {
      name: "Sessions actives",
    });

    expect(within(table).getByText("MacBook Pro")).toBeInTheDocument();

    expect(within(table).getByText("Session actuelle")).toBeInTheDocument();

    expect(within(table).getByText("Appareil inconnu")).toBeInTheDocument();

    expect(within(table).getAllByText("—")).toHaveLength(2);

    fireEvent.click(
      within(table).getByRole("button", {
        name: "Révoquer",
      }),
    );

    expect(onRevoke).toHaveBeenCalledTimes(1);
    expect(onRevoke).toHaveBeenCalledWith(sessions[1]);
  });

  it("affiche un bandeau si un refetch échoue avec des données", () => {
    render(<SessionsView {...defaultProps} sessions={sessions} error={networkError} />);

    expect(
      screen.getByText("Les dernières sessions disponibles restent affichées."),
    ).toBeInTheDocument();

    expect(screen.getByText("MacBook Pro")).toBeInTheDocument();
  });

  it("désactive les révocations pendant une mutation et marque la ligne active", () => {
    render(
      <SessionsView
        {...defaultProps}
        sessions={sessions}
        mutationPending
        revokingSessionId={sessions[1].id}
      />,
    );

    expect(
      screen.getByRole("button", {
        name: "Révocation…",
      }),
    ).toBeDisabled();

    expect(
      screen.getByRole("button", {
        name: "Déconnecter cette session",
      }),
    ).toBeDisabled();
  });

  it("conserve la liste et affiche l’erreur de mutation", () => {
    render(<SessionsView {...defaultProps} sessions={sessions} mutationError={serverError} />);

    expect(screen.getByText("Un problème est survenu de notre côté.")).toBeInTheDocument();

    expect(screen.getByText("Référence : corr-sessions-500")).toBeInTheDocument();

    expect(screen.getByText("MacBook Pro")).toBeInTheDocument();
  });
});
