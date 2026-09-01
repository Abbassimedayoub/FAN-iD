import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { EventSchedule } from "./EventSchedule";
import type { OrganizerEvent } from "./types";

function event(overrides: Partial<OrganizerEvent> = {}): OrganizerEvent {
  return {
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
    ...overrides,
  };
}

it("affiche ancienne date et nouvelle date à venir", () => {
  render(
    <EventSchedule
      event={event({
        status: "POSTPONED",
        postponed_from_starts_at: "2026-09-10T18:00:00Z",
        postponed_from_ends_at: "2026-09-10T20:00:00Z",
      })}
    />,
  );

  expect(screen.getByText(/Ancienne date/)).toBeInTheDocument();

  expect(screen.getByText("Nouvelle date à venir")).toBeInTheDocument();
});

it("affiche la nouvelle programmation quand elle est connue", () => {
  render(
    <EventSchedule
      event={event({
        status: "POSTPONED",
        postponed_from_starts_at: "2026-09-10T18:00:00Z",
        postponed_from_ends_at: "2026-09-10T20:00:00Z",
        postponed_to_starts_at: "2026-09-20T18:00:00Z",
        postponed_to_ends_at: "2026-09-20T20:00:00Z",
        starts_at: "2026-09-20T18:00:00Z",
        ends_at: "2026-09-20T20:00:00Z",
      })}
    />,
  );

  expect(screen.queryByText("Nouvelle date à venir")).not.toBeInTheDocument();

  expect(screen.getByText(/Nouvelle date/)).toBeInTheDocument();
});

it("affiche les horaires au format local JJ/MM/AAAA HH:mm", () => {
  const startsAt = "2026-09-20T16:00:00Z";

  const endsAt = "2026-09-20T18:00:00Z";

  const localStart = new Date(startsAt);

  const twoDigits = (value: number): string => String(value).padStart(2, "0");

  const expectedStart =
    [
      twoDigits(localStart.getDate()),
      twoDigits(localStart.getMonth() + 1),
      localStart.getFullYear(),
    ].join("/") +
    " " +
    [twoDigits(localStart.getHours()), twoDigits(localStart.getMinutes())].join(":");

  render(
    <EventSchedule
      event={event({
        status: "PUBLISHED",
        starts_at: startsAt,
        ends_at: endsAt,
      })}
    />,
  );

  expect(screen.getByText((content) => content.includes(expectedStart))).toBeInTheDocument();

  expect(screen.queryByText(/T16:00:00Z/)).not.toBeInTheDocument();
});
