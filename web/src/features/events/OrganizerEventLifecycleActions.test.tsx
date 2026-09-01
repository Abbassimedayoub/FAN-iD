import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "./api";
import { OrganizerEventLifecycleActions } from "./OrganizerEventLifecycleActions";
import type { OrganizerEvent } from "./types";

const event: OrganizerEvent = {
  id: "event-1",
  organizer_id: "org-1",
  category_id: "football",
  name: "Derby FANID",
  description: "Grand match",
  starts_at: "2026-09-20T18:00:00Z",
  ends_at: "2026-09-20T21:00:00Z",
  postponed_from_starts_at: null,
  postponed_from_ends_at: null,
  postponed_to_starts_at: null,
  postponed_to_ends_at: null,
  venue: "Stade FANID",
  capacity_total: 45000,
  image_url: null,
  status: "PUBLISHED",
  published_at: "2026-08-25T20:00:00Z",
  lifecycle_reason: "",
  lifecycle_changed_at: null,
  version: 3,
  created_at: "2026-08-25T19:00:00Z",
  updated_at: "2026-08-25T20:00:00Z",
};

afterEach(() => {
  vi.restoreAllMocks();
});

it("reporte un événement avec notification demandée", async () => {
  const updated: OrganizerEvent = {
    ...event,
    status: "POSTPONED",
    lifecycle_reason: "Stade indisponible",
    version: 4,
  };

  const postponeSpy = vi.spyOn(api, "postponeEvent").mockResolvedValue(updated);

  const onChanged = vi.fn(async () => undefined);

  render(<OrganizerEventLifecycleActions event={event} onChanged={onChanged} />);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Reporter",
    }),
  );

  fireEvent.change(
    screen
      .getByText("Motif du report")
      .parentElement?.querySelector("textarea") as HTMLTextAreaElement,
    {
      target: {
        value: "Stade indisponible",
      },
    },
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Confirmer le report",
    }),
  );

  await waitFor(() => {
    expect(postponeSpy).toHaveBeenCalledTimes(1);
  });

  const firstPostponeCall = postponeSpy.mock.calls.at(0);

  expect(firstPostponeCall).toBeDefined();

  if (!firstPostponeCall) {
    throw new Error("POSTPONE_CALL_NOT_CAPTURED");
  }

  expect(firstPostponeCall[1].reason).toBe("Stade indisponible");

  expect(firstPostponeCall[1].notify_buyers).toBe(true);

  expect(onChanged).toHaveBeenCalledWith(updated);
});

it("suspend un événement avec un motif", async () => {
  const updated: OrganizerEvent = {
    ...event,
    status: "SUSPENDED",
    lifecycle_reason: "Incident de sécurité",
    version: 4,
  };

  const suspendSpy = vi.spyOn(api, "suspendEvent").mockResolvedValue(updated);

  render(<OrganizerEventLifecycleActions event={event} onChanged={async () => undefined} />);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Suspendre",
    }),
  );

  fireEvent.change(
    screen
      .getByText("Motif de la suspension")
      .parentElement?.querySelector("textarea") as HTMLTextAreaElement,
    {
      target: {
        value: "Incident de sécurité",
      },
    },
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Confirmer la suspension",
    }),
  );

  await waitFor(() => {
    expect(suspendSpy).toHaveBeenCalledWith(event, {
      reason: "Incident de sécurité",
      notify_buyers: true,
    });
  });
});

it("annule avec notification et demande de remboursement", async () => {
  const updated: OrganizerEvent = {
    ...event,
    status: "CANCELLED",
    lifecycle_reason: "Événement annulé",
    version: 4,
  };

  const cancelSpy = vi.spyOn(api, "cancelEvent").mockResolvedValue(updated);

  render(<OrganizerEventLifecycleActions event={event} onChanged={async () => undefined} />);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Annuler",
    }),
  );

  fireEvent.change(
    screen
      .getByText("Motif de l’annulation")
      .parentElement?.querySelector("textarea") as HTMLTextAreaElement,
    {
      target: {
        value: "Événement annulé",
      },
    },
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Annuler l’événement",
    }),
  );

  await waitFor(() => {
    expect(cancelSpy).toHaveBeenCalledWith(event, {
      reason: "Événement annulé",
      notify_buyers: true,
      refund_requested: true,
    });
  });
});

it("désarchive un événement archivé", async () => {
  const archived: OrganizerEvent = {
    ...event,
    status: "ARCHIVED",
    version: 8,
  };

  const updated: OrganizerEvent = {
    ...archived,
    status: "PUBLISHED",
    version: 9,
  };

  const unarchiveSpy = vi.spyOn(api, "unarchiveEvent").mockResolvedValue(updated);

  const onChanged = vi.fn(async () => undefined);

  render(<OrganizerEventLifecycleActions event={archived} onChanged={onChanged} />);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Désarchiver",
    }),
  );

  await waitFor(() => {
    expect(unarchiveSpy).toHaveBeenCalledWith(archived);
  });

  expect(onChanged).toHaveBeenCalledWith(updated);
});
