import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
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
  COMPLETED: {
    label: "Terminé",
    className: "bg-violet-50 text-violet-700",
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
              variant="secondary"
              disabled={archivePending}
              onClick={() => {
                void handleArchive();
              }}
              className="flex-1 border border-[#d6dfe8] px-4 font-semibold text-[#536579] hover:bg-[#f7f9fb]"
            >
              {" "}
              {archivePending ? "Archivage…" : "Archiver"}{" "}
            </Button>
          ) : null}

          {event.status === "ARCHIVED" ? (
            <Button
              type="button"
              variant="secondary"
              disabled={unarchivePending}
              onClick={() => {
                void handleUnarchive();
              }}
              className="flex-1 border border-[#b9d4f6] px-4 font-semibold text-[#1769d2] hover:bg-[#f4f8fe]"
            >
              {" "}
              {unarchivePending ? "Désarchivage…" : "Désarchiver"}{" "}
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
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<OrganizerEventStatus | "ALL">("ALL");
  const [periodFilter, setPeriodFilter] = useState<"ALL" | "UPCOMING" | "PAST">("ALL");
  const [page, setPage] = useState(1);

  const organizerQuery = useQuery({
    queryKey: myOrganizerQueryKey,
    queryFn: fetchMyOrganizer,
  });

  const eventsQuery = useQuery({
    queryKey: eventsQueryKey,
    queryFn: fetchOrganizerEvents,
    enabled: organizerQuery.data?.validation_status === "APPROVED",
  });

  const events = useMemo(() => eventsQuery.data ?? [], [eventsQuery.data]);

  const filteredEvents = useMemo(() => {
    const now = Date.now();
    const needle = search.trim().toLocaleLowerCase("fr-FR");

    return events
      .filter((event) => {
        const startsAt = new Date(event.starts_at).getTime();
        const isUpcoming = Number.isFinite(startsAt) && startsAt >= now;
        const matchesSearch =
          !needle ||
          event.name.toLocaleLowerCase("fr-FR").includes(needle) ||
          event.venue.toLocaleLowerCase("fr-FR").includes(needle);
        const matchesStatus = statusFilter === "ALL" || event.status === statusFilter;
        const matchesPeriod =
          periodFilter === "ALL" ||
          (periodFilter === "UPCOMING" && isUpcoming) ||
          (periodFilter === "PAST" && !isUpcoming);

        return matchesSearch && matchesStatus && matchesPeriod;
      })
      .sort((left, right) => {
        const leftTime = new Date(left.starts_at).getTime();
        const rightTime = new Date(right.starts_at).getTime();
        const leftUpcoming = Number.isFinite(leftTime) && leftTime >= now;
        const rightUpcoming = Number.isFinite(rightTime) && rightTime >= now;

        if (leftUpcoming && rightUpcoming) {
          return leftTime - rightTime;
        }

        if (!leftUpcoming && !rightUpcoming) {
          return rightTime - leftTime;
        }

        return leftUpcoming ? -1 : 1;
      });
  }, [events, periodFilter, search, statusFilter]);

  const pageCount = Math.max(1, Math.ceil(filteredEvents.length / 10));
  const currentPage = Math.min(page, pageCount);
  const pageEvents = filteredEvents.slice((currentPage - 1) * 10, currentPage * 10);

  const breadcrumbs = <span className="text-sm font-semibold text-[#34465c]">Événements</span>;

  async function refresh(): Promise<void> {
    await queryClient.invalidateQueries({
      queryKey: eventsQueryKey,
    });
  }

  function updateSearch(value: string): void {
    setSearch(value);
    setPage(1);
  }

  function updateStatus(value: OrganizerEventStatus | "ALL"): void {
    setStatusFilter(value);
    setPage(1);
  }

  function updatePeriod(value: "ALL" | "UPCOMING" | "PAST"): void {
    setPeriodFilter(value);
    setPage(1);
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
              <Button type="button" onClick={() => void eventsQuery.refetch()} className="mt-5">
                Réessayer
              </Button>
            </Card>
          ) : events.length === 0 ? (
            <Card className="border-dashed p-10 text-center">
              <h2 className="font-sora text-xl font-bold text-[#30445b]">Aucun événement</h2>
              <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#7f8c9b]">
                Créez votre premier événement pour commencer à configurer vos catégories et quotas.
              </p>
            </Card>
          ) : (
            <>
              <Card className="mb-5 p-5">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_220px]">
                  <label className="text-sm font-semibold text-[#40556b]">
                    Rechercher
                    <input
                      value={search}
                      onChange={(event) => updateSearch(event.target.value)}
                      placeholder="Nom ou lieu"
                      className="mt-2 min-h-[44px] w-full rounded-xl border border-[#c9d8ea] bg-white px-4 text-sm font-normal text-[#293c52] outline-none transition focus:border-[#1769d2] focus:ring-4 focus:ring-[#1769d2]/10"
                    />
                  </label>

                  <label className="text-sm font-semibold text-[#40556b]">
                    Statut
                    <select
                      value={statusFilter}
                      onChange={(event) =>
                        updateStatus(event.target.value as OrganizerEventStatus | "ALL")
                      }
                      className="mt-2 min-h-[44px] w-full rounded-xl border border-[#c9d8ea] bg-white px-4 text-sm font-normal text-[#293c52] outline-none transition focus:border-[#1769d2] focus:ring-4 focus:ring-[#1769d2]/10"
                    >
                      <option value="ALL">Tous les statuts</option>
                      {Object.entries(STATUS_CONTENT).map(([value, status]) => (
                        <option key={value} value={value}>
                          {status.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="text-sm font-semibold text-[#40556b]">
                    Période
                    <select
                      value={periodFilter}
                      onChange={(event) =>
                        updatePeriod(event.target.value as "ALL" | "UPCOMING" | "PAST")
                      }
                      className="mt-2 min-h-[44px] w-full rounded-xl border border-[#c9d8ea] bg-white px-4 text-sm font-normal text-[#293c52] outline-none transition focus:border-[#1769d2] focus:ring-4 focus:ring-[#1769d2]/10"
                    >
                      <option value="ALL">Toutes les dates</option>
                      <option value="UPCOMING">À venir</option>
                      <option value="PAST">Passés</option>
                    </select>
                  </label>
                </div>
              </Card>

              {filteredEvents.length === 0 ? (
                <Card className="p-8 text-center text-sm text-[#718195]">
                  Aucun événement ne correspond à ces filtres.
                </Card>
              ) : (
                <>
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-[#5e7083]">
                      {filteredEvents.length} événement{filteredEvents.length > 1 ? "s" : ""} · page{" "}
                      {currentPage} sur {pageCount}
                    </p>
                    <p className="text-xs text-[#7b8998]">
                      Les événements à venir les plus proches apparaissent en premier.
                    </p>
                  </div>

                  <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                    {pageEvents.map((event) => (
                      <EventCard key={event.id} event={event} onArchived={refresh} />
                    ))}
                  </div>

                  {pageCount > 1 ? (
                    <nav
                      aria-label="Pagination des événements"
                      className="mt-7 flex items-center justify-center gap-3"
                    >
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={currentPage === 1}
                        onClick={() => setPage((value) => Math.max(1, value - 1))}
                      >
                        ← Précédent
                      </Button>
                      <span className="text-sm font-semibold text-[#536579]">
                        {currentPage} / {pageCount}
                      </span>
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={currentPage === pageCount}
                        onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
                      >
                        Suivant →
                      </Button>
                    </nav>
                  ) : null}
                </>
              )}
            </>
          )}
        </div>
      </main>
    </OrganizerShell>
  );
}
