import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import * as api from "./api";
import { OrganizerEventLifecycleActions } from "./OrganizerEventLifecycleActions";
import type { OrganizerEvent } from "./types";

const event: OrganizerEvent = {
  id: "event-1",
  organizer_id: "org-1",
  category_id: "cat-1",
  name: "Finale FANID",
  description: "",
  starts_at: "2026-09-10T18:00:00Z",
  ends_at: "2026-09-10T20:00:00Z",
  postponed_from_starts_at: null,
  postponed_from_ends_at: null,
  postponed_to_starts_at: null,
  postponed_to_ends_at: null,
  venue: "Paris",
  capacity_total: 100,
  image_url: null,
  status: "PUBLISHED",
  published_at: "2026-08-01T10:00:00Z",
  lifecycle_reason: "",
  lifecycle_changed_at: null,
  version: 1,
  created_at: "2026-08-01T08:00:00Z",
  updated_at: "2026-08-01T08:00:00Z",
};

it("permet de reporter sans nouvelle date", async () => {
  const updated: OrganizerEvent = {
    ...event,
    status: "POSTPONED",
    postponed_from_starts_at: event.starts_at,
    postponed_from_ends_at: event.ends_at,
    lifecycle_reason: "Nouvelle date en attente",
    version: 2,
  };

  const spy = vi.spyOn(api, "postponeEvent").mockResolvedValue(updated);

  render(<OrganizerEventLifecycleActions event={event} onChanged={async () => undefined} />);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Reporter",
    }),
  );

  const reasonLabel = screen.getByText("Motif du report");

  const textarea = reasonLabel.parentElement?.querySelector("textarea") as HTMLTextAreaElement;

  fireEvent.change(textarea, {
    target: {
      value: "Nouvelle date en attente",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Reporter sans nouvelle date",
    }),
  );

  await vi.waitFor(() => {
    expect(spy).toHaveBeenCalled();
  });

  expect(spy.mock.calls[0]?.[1]).toMatchObject({
    starts_at: null,
    ends_at: null,
    reason: "Nouvelle date en attente",
  });
});
