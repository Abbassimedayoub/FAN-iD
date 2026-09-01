import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import * as api from "./api";
import { OrganizerEventLifecycleActions } from "./OrganizerEventLifecycleActions";
import type { OrganizerEvent } from "./types";

const postponedEvent: OrganizerEvent = {
  id: "event-postponed",
  organizer_id: "org-1",
  category_id: "cat-1",
  name: "Finale reportée",
  description: "",
  starts_at: "2026-09-10T18:00:00Z",
  ends_at: "2026-09-10T20:00:00Z",
  postponed_from_starts_at: "2026-09-10T18:00:00Z",
  postponed_from_ends_at: "2026-09-10T20:00:00Z",
  postponed_to_starts_at: null,
  postponed_to_ends_at: null,
  venue: "Paris",
  capacity_total: 100,
  image_url: null,
  status: "POSTPONED",
  published_at: "2026-08-01T10:00:00Z",
  lifecycle_reason: "Nouvelle date en attente",
  lifecycle_changed_at: "2026-09-01T10:00:00Z",
  version: 2,
  created_at: "2026-08-01T08:00:00Z",
  updated_at: "2026-09-01T10:00:00Z",
};

it("propose de définir une nouvelle date quand elle est encore inconnue", async () => {
  const updated: OrganizerEvent = {
    ...postponedEvent,
    starts_at: "2026-09-20T18:00:00Z",
    ends_at: "2026-09-20T20:00:00Z",
    postponed_to_starts_at: "2026-09-20T18:00:00Z",
    postponed_to_ends_at: "2026-09-20T20:00:00Z",
    lifecycle_reason: postponedEvent.lifecycle_reason,
    version: 3,
  };

  const spy = vi.spyOn(api, "postponeEvent").mockResolvedValue(updated);

  render(
    <OrganizerEventLifecycleActions event={postponedEvent} onChanged={async () => undefined} />,
  );

  fireEvent.click(
    screen.getByRole("button", {
      name: "Définir une nouvelle date",
    }),
  );

  expect(
    screen.queryByRole("button", {
      name: "Reporter sans nouvelle date",
    }),
  ).not.toBeInTheDocument();

  const start = screen.getByLabelText("Nouvelle date de début");

  const end = screen.getByLabelText("Nouvelle date de fin");

  expect(start).toHaveValue("");
  expect(end).toHaveValue("");

  expect(screen.queryByText("Motif du report")).not.toBeInTheDocument();

  fireEvent.change(start, {
    target: {
      value: "2026-09-20T18:00",
    },
  });

  expect(end).toHaveValue("2026-09-20T21:00");

  const form = start.closest("form");

  expect(form).not.toBeNull();

  fireEvent.submit(form!);

  await waitFor(() => {
    expect(spy).toHaveBeenCalled();
  });

  expect(spy.mock.calls[0]?.[1]).toMatchObject({
    starts_at: new Date("2026-09-20T18:00").toISOString(),
    ends_at: new Date("2026-09-20T21:00").toISOString(),
    reason: "",
  });
});
