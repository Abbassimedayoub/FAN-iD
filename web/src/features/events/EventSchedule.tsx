import type { OrganizerEvent } from "./types";

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const twoDigits = (number: number): string => String(number).padStart(2, "0");

  /*
   * L'API transporte les instants en UTC.
   * L'interface affiche toujours l'heure locale
   * de l'appareil, exactement comme Flutter.
   */
  return (
    [twoDigits(date.getDate()), twoDigits(date.getMonth() + 1), date.getFullYear()].join("/") +
    " " +
    [twoDigits(date.getHours()), twoDigits(date.getMinutes())].join(":")
  );
}

function range(startsAt: string, endsAt: string): string {
  return `${formatDate(startsAt)} → ${formatDate(endsAt)}`;
}

export function EventSchedule({
  event,
  compact = false,
}: {
  event: OrganizerEvent;
  compact?: boolean;
}) {
  if (event.status !== "POSTPONED") {
    return (
      <div className={compact ? "text-sm" : "space-y-1 text-sm"}>
        <span>{range(event.starts_at, event.ends_at)}</span>
      </div>
    );
  }

  const oldStartsAt = event.postponed_from_starts_at ?? event.starts_at;

  const oldEndsAt = event.postponed_from_ends_at ?? event.ends_at;

  const hasNewSchedule = Boolean(event.postponed_to_starts_at && event.postponed_to_ends_at);

  return (
    <div className={compact ? "space-y-1 text-sm" : "space-y-2 text-sm"}>
      <p>
        <span className="font-semibold">Ancienne date :</span> {range(oldStartsAt, oldEndsAt)}
      </p>

      <p>
        <span className="font-semibold">Nouvelle date :</span>{" "}
        {hasNewSchedule ? (
          range(event.postponed_to_starts_at!, event.postponed_to_ends_at!)
        ) : (
          <span className="font-semibold text-blue-700">Nouvelle date à venir</span>
        )}
      </p>
    </div>
  );
}
