import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, Spinner } from "@/components/primitives";
import { EventSchedule } from "@/features/events/EventSchedule";
import type { OrganizerEvent, TicketCategory } from "@/features/events/types";
import { toAppError } from "@/lib/errors";
import { httpClient } from "@/lib/httpClient";

interface AdminOrganizerEvent extends OrganizerEvent {
  ticket_categories: TicketCategory[];
}

interface EventPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: AdminOrganizerEvent[];
}

const STATUS_LABELS: Record<OrganizerEvent["status"], string> = {
  DRAFT: "Brouillon",
  PUBLISHED: "Publié",
  POSTPONED: "Reporté",
  SUSPENDED: "Suspendu",
  CANCELLED: "Annulé",
  ARCHIVED: "Archivé",
};

function normalizeNextUrl(value: string): string {
  try {
    const parsed = new URL(value, window.location.origin);

    return parsed.pathname + parsed.search;
  } catch {
    return value;
  }
}

async function fetchAdminOrganizerEvents(organizerId: string): Promise<AdminOrganizerEvent[]> {
  const endpoint = `/api/v1/admin/organizers/` + `${organizerId}/events`;

  const first = await httpClient.get<EventPage | AdminOrganizerEvent[]>(endpoint);

  /*
   * Le backend standard est paginé.
   * On accepte également une liste brute afin
   * que cette vue reste robuste si la pagination
   * est désactivée localement.
   */
  if (Array.isArray(first.data)) {
    return first.data;
  }

  const items = [...first.data.results];

  let next = first.data.next;

  while (next) {
    const page = await httpClient.get<EventPage>(normalizeNextUrl(next));

    items.push(...page.data.results);

    next = page.data.next;
  }

  return items;
}

function formatPrice(cents: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(cents / 100);
}

function TicketSales({ tickets }: { tickets: TicketCategory[] }) {
  if (tickets.length === 0) {
    return <p className="text-sm text-navy/50">Aucun type de billet configuré.</p>;
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-3 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-navy/50">
        <span>Type</span>
        <span>Prix</span>
        <span>Vendus</span>
      </div>

      {tickets.map((ticket) => (
        <div
          key={ticket.id}
          className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 border-t border-slate-100 px-4 py-3 text-sm"
        >
          <span className="truncate font-semibold text-navy">{ticket.name}</span>

          <span className="whitespace-nowrap font-medium text-navy/70">
            {formatPrice(ticket.unit_price_cents)}
          </span>

          <span className="whitespace-nowrap font-bold text-[#1769d2]">
            {ticket.sold_count}/{ticket.quota}
          </span>
        </div>
      ))}
    </div>
  );
}

export function AdminOrganizerEventsPanel({ organizerId }: { organizerId: string }) {
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["admin", "organizer", organizerId, "events"],
    queryFn: () => fetchAdminOrganizerEvents(organizerId),
    enabled: Boolean(organizerId),
  });

  const error = query.isError ? toAppError(query.error) : null;

  const events = query.data ?? [];

  return (
    <section className="mx-auto w-full max-w-4xl px-6 pb-6 md:px-8">
      <Card>
        <div>
          <h2 className="font-sora text-lg font-semibold text-navy">Événements créés</h2>

          <p className="mt-1 text-sm text-navy/50">Consultation administrative en lecture seule.</p>
        </div>

        {query.isPending ? (
          <div className="mt-6">
            <Spinner label="Chargement des événements" />
          </div>
        ) : error ? (
          <div role="alert" className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-semibold text-red-700">
              Impossible de charger les événements.
            </p>

            <p className="mt-1 text-xs text-red-600">{error.message}</p>

            <Button
              type="button"
              className="mt-3"
              onClick={() => {
                void query.refetch();
              }}
            >
              Réessayer
            </Button>
          </div>
        ) : events.length === 0 ? (
          <p className="mt-5 text-sm text-navy/55">
            Cet organisateur n’a encore créé aucun événement.
          </p>
        ) : (
          <div className="mt-5 space-y-4">
            {events.map((event) => {
              const expanded = expandedEventId === event.id;

              return (
                <article
                  key={event.id}
                  className="overflow-hidden rounded-xl border border-slate-200"
                >
                  <div className="p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-navy">{event.name}</h3>

                        <div className="mt-2 text-navy/65">
                          <EventSchedule event={event} compact />
                        </div>

                        {event.venue ? (
                          <p className="mt-2 text-sm text-navy/55">{event.venue}</p>
                        ) : null}
                      </div>

                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                        {STATUS_LABELS[event.status]}
                      </span>
                    </div>

                    <div className="mt-4 flex justify-end">
                      <Button
                        type="button"
                        className="border border-slate-200 bg-white text-navy hover:bg-slate-50"
                        onClick={() => {
                          setExpandedEventId(expanded ? null : event.id);
                        }}
                      >
                        {expanded ? "Masquer les détails" : "Voir les détails"}
                      </Button>
                    </div>
                  </div>

                  {expanded ? (
                    <div className="border-t border-slate-200 bg-slate-50/60 p-4">
                      <h4 className="mb-3 text-sm font-bold text-navy">Billetterie</h4>

                      <TicketSales tickets={event.ticket_categories} />
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </Card>
    </section>
  );
}
