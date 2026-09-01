import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchOrganizerScanners, type OrganizerScanner } from "@/features/organizers/scanners";

import { assignEventScanner, fetchEventScannerAssignments, unassignEventScanner } from "./api";
import { OrganizerEventScannerAssignments } from "./OrganizerEventScannerAssignments";
import type { EventScannerAssignment, OrganizerEvent } from "./types";

vi.mock("@/features/organizers/scanners", () => ({
  organizerScannersQueryKey: ["organizing", "organizer-scanners"],
  fetchOrganizerScanners: vi.fn(),
}));

vi.mock("./api", () => ({
  fetchEventScannerAssignments: vi.fn(),
  assignEventScanner: vi.fn(),
  unassignEventScanner: vi.fn(),
}));

const fetchAssignmentsMock = vi.mocked(fetchEventScannerAssignments);

const fetchScannersMock = vi.mocked(fetchOrganizerScanners);

const assignScannerMock = vi.mocked(assignEventScanner);

const unassignScannerMock = vi.mocked(unassignEventScanner);

const event: OrganizerEvent = {
  id: "event-1",
  organizer_id: "org-1",
  category_id: "football",
  name: "Derby",
  description: "",
  starts_at: "2026-09-20T18:00:00Z",
  ends_at: "2026-09-20T21:00:00Z",
  postponed_from_starts_at: null,
  postponed_from_ends_at: null,
  postponed_to_starts_at: null,
  postponed_to_ends_at: null,
  venue: "Stade",
  capacity_total: 1000,
  image_url: null,
  status: "PUBLISHED",
  published_at: "2026-08-25T20:00:00Z",
  lifecycle_reason: "",
  lifecycle_changed_at: null,
  version: 7,
  created_at: "2026-08-25T19:00:00Z",
  updated_at: "2026-08-25T20:00:00Z",
};

function makeScanner(values: Partial<OrganizerScanner>): OrganizerScanner {
  return {
    id: "scanner-default",
    user_id: "user-default",
    first_name: "Scanner",
    last_name: "Default",
    email: "scanner@example.test",
    phone: null,
    status: "ACTIVE",
    scanner_email_sent_at: null,
    organizer_email_sent_at: null,
    opened_at: null,
    activated_at: null,
    removed_at: null,
    archived_at: null,
    password_help_pending: false,
    password_help_requested_at: null,
    created_at: "2026-08-20T12:00:00Z",
    updated_at: "2026-08-20T12:00:00Z",
    version: 1,
    ...values,
  };
}

function makeAssignment(values: Partial<EventScannerAssignment>): EventScannerAssignment {
  return {
    assignment_id: "assignment-default",
    scanner_id: "scanner-default",
    first_name: "Scanner",
    last_name: "Default",
    email: "scanner@example.test",
    status: "ACTIVE",
    scanner_version: 1,
    assigned_at: "2026-08-30T12:00:00Z",
    ...values,
  };
}

function renderWithQueryClient(node: ReactNode) {
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

  return render(<QueryClientProvider client={queryClient}>{node}</QueryClientProvider>);
}

describe("OrganizerEventScannerAssignments", () => {
  beforeEach(() => {
    fetchAssignmentsMock.mockResolvedValue([]);

    fetchScannersMock.mockResolvedValue([]);

    assignScannerMock.mockResolvedValue(makeAssignment({}));

    unassignScannerMock.mockResolvedValue();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("bloque toute affectation sur un brouillon", () => {
    renderWithQueryClient(
      <OrganizerEventScannerAssignments
        event={{
          ...event,
          status: "DRAFT",
          published_at: null,
        }}
      />,
    );

    expect(
      screen.getByText(/Publiez l’événement avant d’affecter des scanners/),
    ).toBeInTheDocument();

    expect(fetchAssignmentsMock).not.toHaveBeenCalled();

    expect(fetchScannersMock).not.toHaveBeenCalled();
  });

  it("affiche simplement qu aucun scanner n existe au lieu de l erreur des affectations", async () => {
    fetchAssignmentsMock.mockRejectedValueOnce(new Error("assignment endpoint unavailable"));

    fetchScannersMock.mockResolvedValueOnce([]);

    renderWithQueryClient(<OrganizerEventScannerAssignments event={event} />);

    expect(await screen.findByText("Aucun scanner affecté")).toBeInTheDocument();

    expect(screen.getByText(/Invitez un scanner depuis la page Scanners/)).toBeInTheDocument();

    expect(
      screen.queryByText("Impossible de charger les scanners affectés."),
    ).not.toBeInTheDocument();
  });

  it("affecte puis retire un scanner et filtre les statuts interdits", async () => {
    fetchAssignmentsMock.mockResolvedValue([
      makeAssignment({
        assignment_id: "assignment-1",
        scanner_id: "scanner-1",
        first_name: "Amine",
        last_name: "Affecté",
        email: "amine@example.test",
      }),
    ]);

    fetchScannersMock.mockResolvedValue([
      makeScanner({
        id: "scanner-1",
        first_name: "Amine",
        last_name: "Affecté",
        email: "amine@example.test",
      }),
      makeScanner({
        id: "scanner-2",
        first_name: "Sana",
        last_name: "Disponible",
        email: "sana@example.test",
        status: "EMAIL_SENT",
      }),
      makeScanner({
        id: "scanner-3",
        first_name: "Compte",
        last_name: "Supprimé",
        status: "DELETED",
      }),
      makeScanner({
        id: "scanner-4",
        first_name: "Invitation",
        last_name: "Annulée",
        status: "INVITATION_CANCELLED",
      }),
    ]);

    assignScannerMock.mockResolvedValue(
      makeAssignment({
        assignment_id: "assignment-2",
        scanner_id: "scanner-2",
        first_name: "Sana",
        last_name: "Disponible",
        email: "sana@example.test",
        status: "EMAIL_SENT",
      }),
    );

    renderWithQueryClient(<OrganizerEventScannerAssignments event={event} />);

    expect(await screen.findByText("Amine Affecté")).toBeInTheDocument();

    expect(await screen.findByText("Sana Disponible")).toBeInTheDocument();

    expect(screen.queryByText("Compte Supprimé")).not.toBeInTheDocument();

    expect(screen.queryByText("Invitation Annulée")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Affecter Sana Disponible",
      }),
    );

    await waitFor(() => {
      expect(assignScannerMock).toHaveBeenCalledWith("event-1", "scanner-2");
    });

    expect(
      await screen.findByRole("button", {
        name: "Retirer Sana Disponible",
      }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", {
        name: "Retirer Sana Disponible",
      }),
    );

    await waitFor(() => {
      expect(unassignScannerMock).toHaveBeenCalledWith("event-1", "scanner-2");
    });

    expect(
      await screen.findByRole("button", {
        name: "Affecter Sana Disponible",
      }),
    ).toBeInTheDocument();
  });

  it("autorise aussi les affectations sur un événement reporté", async () => {
    fetchScannersMock.mockResolvedValue([
      makeScanner({
        id: "scanner-postponed",
        first_name: "Nadia",
        last_name: "Report",
        status: "OPENED",
      }),
    ]);

    renderWithQueryClient(
      <OrganizerEventScannerAssignments
        event={{
          ...event,
          status: "POSTPONED",
        }}
      />,
    );

    expect(
      await screen.findByRole("button", {
        name: "Affecter Nadia Report",
      }),
    ).toBeInTheDocument();
  });

  it("conserve la liste en lecture sans nouveaux ajouts si suspendu", async () => {
    fetchAssignmentsMock.mockResolvedValue([
      makeAssignment({
        assignment_id: "assignment-suspended",
        scanner_id: "scanner-suspended",
        first_name: "Ali",
        last_name: "Terrain",
      }),
    ]);

    renderWithQueryClient(
      <OrganizerEventScannerAssignments
        event={{
          ...event,
          status: "SUSPENDED",
        }}
      />,
    );

    expect(await screen.findByText("Ali Terrain")).toBeInTheDocument();

    expect(
      screen.getByText(/Les nouvelles affectations sont disponibles uniquement/),
    ).toBeInTheDocument();

    expect(fetchScannersMock).not.toHaveBeenCalled();
  });
});
