import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Card, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";

import { EventSchedule } from "./EventSchedule";
import { fetchOrganizerEvent, fetchTicketCategories } from "./api";
import { OrganizerEventDeleteButton } from "./OrganizerEventDeleteButton";
import { OrganizerEventLifecycleActions } from "./OrganizerEventLifecycleActions";
import { OrganizerEventScannerAssignments } from "./OrganizerEventScannerAssignments";
import type { OrganizerEventStatus } from "./types";
import { eventImageUrl } from "./eventImageUrl";

const EVENT_STATUS_LABELS: Record<OrganizerEventStatus, string> = {
  DRAFT: "Brouillon",
  PUBLISHED: "Publié",
  POSTPONED: "Reporté",
  SUSPENDED: "Suspendu",
  CANCELLED: "Annulé",
  ARCHIVED: "Archivé",
};

function formatDate(value: string): string {
  const date = new Date(value);

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "long",
    timeStyle: "short",
  }).format(date);
}

export function OrganizerEventDetailPage() {
  const queryClient = useQueryClient();

  const navigate = useNavigate();

  const { eventId } = useParams<{
    eventId: string;
  }>();

  const eventQuery = useQuery({
    queryKey: ["catalog", "event", eventId],
    queryFn: () => {
      if (!eventId) {
        throw new Error("EVENT_ID_REQUIRED");
      }

      return fetchOrganizerEvent(eventId);
    },
    enabled: Boolean(eventId),
  });

  const categoriesQuery = useQuery({
    queryKey: ["catalog", "event", eventId, "ticket-categories"],
    queryFn: () => {
      if (!eventId) {
        throw new Error("EVENT_ID_REQUIRED");
      }

      return fetchTicketCategories(eventId);
    },
    enabled: Boolean(eventId) && Boolean(eventQuery.data),
  });

  const event = eventQuery.data;

  return (
    <OrganizerShell
      activeItem="events"
      breadcrumbs={
        <div className="flex items-center gap-2 text-sm">
          <Link to="/organizer/events" className="font-medium text-[#8a96a5] hover:text-[#1769d2]">
            Événements
          </Link>

          <span aria-hidden="true">/</span>

          <span className="font-semibold text-[#34465c]">Détail</span>
        </div>
      }
    >
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[980px]">
          {eventQuery.isPending ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <Spinner label="Chargement de l’événement" />
            </div>
          ) : eventQuery.isError || !event ? (
            <Card className="p-8 text-center">Événement introuvable.</Card>
          ) : (
            <div className="space-y-5">
              <Card className="overflow-hidden p-0">
                {event.image_url ? (
                  <img
                    src={eventImageUrl(event.image_url) ?? undefined}
                    alt=""
                    className="aspect-[2/1] w-full object-cover"
                  />
                ) : null}

                <div className="p-6 sm:p-8">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h1 className="font-sora text-3xl font-bold text-[#293c52]">{event.name}</h1>

                      <EventSchedule event={event} compact />
                    </div>

                    {event.status === "DRAFT" ? (
                      <div className="flex flex-wrap gap-2">
                        <Link
                          to={`/organizer/events/${event.id}/continue`}
                          className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
                        >
                          Continuer la création
                        </Link>

                        <Link
                          to={`/organizer/events/${event.id}/edit`}
                          className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[#b9cbe0] bg-white px-5 text-sm font-semibold text-[#405b78]"
                        >
                          Modifier
                        </Link>

                        <OrganizerEventDeleteButton
                          event={event}
                          onDeleted={async () => {
                            await queryClient.invalidateQueries({
                              queryKey: ["catalog", "organizer-events"],
                            });

                            navigate("/organizer/events", {
                              replace: true,
                            });
                          }}
                        />
                      </div>
                    ) : null}
                  </div>

                  {event.description ? (
                    <p className="mt-6 whitespace-pre-line text-sm leading-7 text-[#66788b]">
                      {event.description}
                    </p>
                  ) : null}

                  <dl className="mt-7 grid gap-5 border-t border-[#edf0f3] pt-6 sm:grid-cols-3">
                    <div>
                      <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[#98a3af]">
                        Statut
                      </dt>
                      <dd className="mt-2 font-semibold text-[#40556b]">
                        {EVENT_STATUS_LABELS[event.status]}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[#98a3af]">
                        Lieu
                      </dt>
                      <dd className="mt-2 font-semibold text-[#40556b]">{event.venue || "—"}</dd>
                    </div>

                    <div>
                      <dt className="text-xs font-bold uppercase tracking-[0.1em] text-[#98a3af]">
                        Capacité
                      </dt>
                      <dd className="mt-2 font-semibold text-[#40556b]">
                        {event.capacity_total ?? "—"}
                      </dd>
                    </div>
                  </dl>
                </div>
              </Card>

              {event.lifecycle_reason ? (
                <Card className="border-[#dce6f0] bg-[#f8fbfe] p-6">
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-[#8090a2]">
                    Dernier changement
                  </p>

                  <p className="mt-2 text-sm leading-6 text-[#536579]">{event.lifecycle_reason}</p>

                  {event.lifecycle_changed_at ? (
                    <p className="mt-2 text-xs text-[#8a97a5]">
                      {formatDate(event.lifecycle_changed_at)}
                    </p>
                  ) : null}
                </Card>
              ) : null}

              <OrganizerEventLifecycleActions
                event={event}
                onChanged={async (updated) => {
                  queryClient.setQueryData(["catalog", "event", updated.id], updated);

                  await queryClient.invalidateQueries({
                    queryKey: ["catalog", "organizer-events"],
                  });
                }}
              />

              <Card className="p-6 sm:p-8">
                <h2 className="font-sora text-lg font-bold text-[#30445b]">Catégories & quotas</h2>

                {categoriesQuery.isPending ? (
                  <div className="mt-6">
                    <Spinner label="Chargement des catégories" />
                  </div>
                ) : categoriesQuery.data?.length ? (
                  <div className="mt-5 divide-y divide-[#edf0f3]">
                    {categoriesQuery.data.map((category) => (
                      <div
                        key={category.id}
                        className="flex flex-wrap items-center justify-between gap-4 py-4"
                      >
                        <div>
                          <p className="font-semibold text-[#40556b]">{category.name}</p>

                          <p className="mt-1 text-xs text-[#8b97a4]">
                            Quota : {category.quota} · Vendus : {category.sold_count}
                          </p>
                        </div>

                        <p className="font-bold text-[#1769d2]">
                          {(category.unit_price_cents / 100).toFixed(2)} €
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-[#8793a1]">Aucune catégorie configurée.</p>
                )}
              </Card>

              <OrganizerEventScannerAssignments event={event} />

              <Link
                to="/organizer/events"
                className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[#d6dfe8] bg-white px-5 text-sm font-semibold text-[#536579]"
              >
                ← Retour aux événements
              </Link>
            </div>
          )}
        </div>
      </main>
    </OrganizerShell>
  );
}
