import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, Card, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";
import { fetchMyOrganizer, myOrganizerQueryKey } from "@/features/organizers/myOrganizer";
import { toAppError } from "@/lib/errors";

import { EventSchedule } from "./EventSchedule";
import { eventImageUrl } from "./eventImageUrl";
import { archiveEvent, fetchOrganizerEvents, unarchiveEvent } from "./api";
import { OrganizerEventDeleteButton } from "./OrganizerEventDeleteButton";
import type { OrganizerEvent, OrganizerEventStatus } from "./types";

const eventsQueryKey = ["catalog", "organizer-events"] as const;

const STATUS_CONTENT: Record<
  OrganizerEventStatus,
  {
    label: string;
    className: string;
  }
> = {
  DRAFT: {
    label: "Brouillon",
    className: "bg-amber-50 text-amber-700",
  },
  PUBLISHED: {
    label: "Publié",
    className: "bg-emerald-50 text-emerald-700",
  },
  POSTPONED: {
    label: "Reporté",
    className: "bg-blue-50 text-blue-700",
  },
  SUSPENDED: {
    label: "Suspendu",
    className: "bg-orange-50 text-orange-700",
  },
  CANCELLED: {
    label: "Annulé",
    className: "bg-red-50 text-red-700",
  },
  ARCHIVED: {
    label: "Archivé",
    className: "bg-slate-100 text-slate-600",
  },
};

function EventCard({
  event,
  onArchived,
}: {
  event: OrganizerEvent;
  onArchived: () => Promise<void>;
}) {
  const [archivePending, setArchivePending] = useState(false);

  const [archiveError, setArchiveError] = useState<string | null>(null);

  const [unarchivePending, setUnarchivePending] = useState(false);

  const [unarchiveError, setUnarchiveError] = useState<string | null>(null);

  const status = STATUS_CONTENT[event.status];

  async function handleArchive(): Promise<void> {
    setArchivePending(true);
    setArchiveError(null);

    try {
      await archiveEvent(event);
      await onArchived();
    } catch (error) {
      setArchiveError(toAppError(error).message);
    } finally {
      setArchivePending(false);
    }
  }

  async function handleUnarchive(): Promise<void> {
    setUnarchivePending(true);
    setUnarchiveError(null);

    try {
      await unarchiveEvent(event);
      await onArchived();
    } catch (error) {
      setUnarchiveError(toAppError(error).message);
    } finally {
      setUnarchivePending(false);
    }
  }

  return (
    <Card className="overflow-hidden border-[#e0e7ee] p-0 shadow-[0_10px_28px_rgba(23,45,74,0.05)]">
      {event.image_url ? (
        <div className="aspect-[2/1] overflow-hidden bg-[#edf2f7]">
          <img
            src={eventImageUrl(event.image_url) ?? undefined}
            alt=""
            className="h-full w-full object-cover"
          />
        </div>
      ) : (
        <div className="flex aspect-[2/1] items-center justify-center bg-[#eef3f7]">
          <span
            aria-hidden="true"
            className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-[#1769d2] shadow-sm"
          >
            <svg
              viewBox="0 0 24 24"
              className="h-6 w-6"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="3" y="5" width="18" height="16" rx="2" />
              <path d="M8 3v4M16 3v4M3 10h18" />
            </svg>
          </span>
        </div>
      )}

      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate font-sora text-lg font-bold text-[#293c52]">{event.name}</h2>

            <EventSchedule event={event} compact />
          </div>

          <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${status.className}`}>
            {status.label}
          </span>
        </div>

        <div className="mt-4 space-y-2 text-sm">
          <div className="flex items-center justify-between gap-4">
            <span className="text-[#8995a3]">Lieu</span>

            <span className="truncate font-semibold text-[#536579]">
              {event.venue || "Non renseigné"}
            </span>
          </div>

          <div className="flex items-center justify-between gap-4">
            <span className="text-[#8995a3]">Capacité</span>

            <span className="font-semibold text-[#536579]">{event.capacity_total ?? "—"}</span>
          </div>
        </div>

        {event.description ? (
          <p className="mt-4 line-clamp-2 text-sm leading-6 text-[#718195]">{event.description}</p>
        ) : null}

        <div className="mt-5 flex flex-wrap gap-2 border-t border-[#edf0f3] pt-4">
          <Link
            to={`/organizer/events/${event.id}`}
            className="inline-flex min-h-[42px] flex-1 items-center justify-center rounded-xl border border-[#d6dfe8] bg-white px-4 text-sm font-semibold text-[#42566b] transition hover:border-[#1769d2]/30 hover:text-[#1769d2]"
          >
            Voir
          </Link>

          {event.status === "DRAFT" ? (
            <>
              <Link
                to={`/organizer/events/${event.id}/continue`}
                className="inline-flex min-h-[42px] flex-1 items-center justify-center rounded-xl bg-[#1769d2] px-4 text-sm font-semibold text-white transition hover:bg-[#125bb9]"
              >
                Continuer la création
              </Link>

              <Link
                to={`/organizer/events/${event.id}/edit`}
                className="inline-flex min-h-[42px] flex-1 items-center justify-center rounded-xl border border-[#b9cbe0] bg-white px-4 text-sm font-semibold text-[#405b78] transition hover:bg-[#f5f8fc]"
              >
                Modifier
              </Link>
            </>
          ) : null}

          {event.status === "DRAFT" ? (
            <OrganizerEventDeleteButton event={event} onDeleted={onArchived} />
          ) : null}

          {event.status === "PUBLISHED" ? (
            <Button
              type="button"
              disabled={archivePending}
              onClick={() => {
                void handleArchive();
              }}
              className="flex-1 border border-[#d6dfe8] bg-white px-4 font-semibold text-[#536579] hover:bg-[#f7f9fb]"
            >
              {archivePending ? "Archivage…" : "Archiver"}
            </Button>
          ) : null}

          {event.status === "ARCHIVED" ? (
            <Button
              type="button"
              disabled={unarchivePending}
              onClick={() => {
                void handleUnarchive();
              }}
              className="flex-1 border border-[#b9d4f6] bg-white px-4 font-semibold text-[#1769d2] hover:bg-[#f4f8fe]"
            >
              {unarchivePending ? "Désarchivage…" : "Désarchiver"}
            </Button>
          ) : null}
        </div>

        {archiveError ? (
          <p role="alert" className="mt-3 text-xs font-medium text-red-600">
            {archiveError}
          </p>
        ) : null}

        {unarchiveError ? (
          <p role="alert" className="mt-3 text-xs font-medium text-red-600">
            {unarchiveError}
          </p>
        ) : null}
      </div>
    </Card>
  );
}

export function OrganizerEventsPage() {
  const queryClient = useQueryClient();

  const organizerQuery = useQuery({
    queryKey: myOrganizerQueryKey,
    queryFn: fetchMyOrganizer,
  });

  const eventsQuery = useQuery({
    queryKey: eventsQueryKey,
    queryFn: fetchOrganizerEvents,
    enabled: organizerQuery.data?.validation_status === "APPROVED",
  });

  const breadcrumbs = <span className="text-sm font-semibold text-[#34465c]">Événements</span>;

  async function refresh(): Promise<void> {
    await queryClient.invalidateQueries({
      queryKey: eventsQueryKey,
    });
  }

  if (organizerQuery.isPending) {
    return (
      <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
        <div className="flex min-h-[520px] items-center justify-center">
          <Spinner label="Chargement des événements" />
        </div>
      </OrganizerShell>
    );
  }

  if (organizerQuery.isError || !organizerQuery.data) {
    return (
      <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
        <main className="p-6 lg:p-10">
          <Card className="mx-auto max-w-xl p-8 text-center">
            <h1 className="font-sora text-2xl font-bold text-navy">
              Espace organisateur indisponible
            </h1>
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  if (organizerQuery.data.validation_status !== "APPROVED") {
    return (
      <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
        <main className="p-6 lg:p-10">
          <Card className="mx-auto max-w-xl p-8 text-center">
            <h1 className="font-sora text-2xl font-bold text-navy">
              Gestion des événements indisponible
            </h1>

            <p className="mt-3 text-sm leading-6 text-navy/55">
              Votre organisation doit être approuvée avant de gérer des événements.
            </p>
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  return (
    <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[1180px]">
          <header className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="font-sora text-[28px] font-bold tracking-[-0.025em] text-[#26384f]">
                Mes événements
              </h1>

              <p className="mt-2 text-sm text-[#778596]">
                Créez, consultez et gérez les événements de votre organisation.
              </p>
            </div>

            <Link
              to="/organizer/events/new"
              className="inline-flex min-h-[46px] shrink-0 items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(23,105,210,0.18)] transition hover:bg-[#125bb9]"
            >
              <span aria-hidden="true" className="mr-2 text-lg">
                +
              </span>
              Nouvel événement
            </Link>
          </header>

          {eventsQuery.isPending ? (
            <div className="flex min-h-[380px] items-center justify-center">
              <Spinner label="Chargement des événements" />
            </div>
          ) : eventsQuery.isError ? (
            <Card className="p-8 text-center">
              <h2 className="font-sora text-xl font-bold text-[#30445b]">
                Impossible de charger les événements
              </h2>

              <p className="mt-2 text-sm text-[#7b8998]">Réessayez dans quelques instants.</p>

              <Button
                type="button"
                onClick={() => {
                  void eventsQuery.refetch();
                }}
                className="mt-5"
              >
                Réessayer
              </Button>
            </Card>
          ) : eventsQuery.data.length === 0 ? (
            <Card className="border-dashed p-10 text-center">
              <span
                aria-hidden="true"
                className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#eef5ff] text-2xl font-bold text-[#1769d2]"
              >
                +
              </span>

              <h2 className="mt-5 font-sora text-xl font-bold text-[#30445b]">Aucun événement</h2>

              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#7f8c9b]">
                Créez votre premier événement pour commencer à configurer vos catégories et quotas.
              </p>

              <Link
                to="/organizer/events/new"
                className="mt-6 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
              >
                Créer un événement
              </Link>
            </Card>
          ) : (
            <>
              <div className="mb-4 flex items-center justify-between gap-4">
                <p className="text-sm font-semibold text-[#5e7083]">
                  {eventsQuery.data.length} événement
                  {eventsQuery.data.length > 1 ? "s" : ""}
                </p>
              </div>

              <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {eventsQuery.data.map((event) => (
                  <EventCard key={event.id} event={event} onArchived={refresh} />
                ))}
              </div>
            </>
          )}
        </div>
      </main>
    </OrganizerShell>
  );
}
