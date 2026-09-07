import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Card, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";

import { fetchEventLiveDashboard } from "./api";

function formatDate(value: string | null): string {
  if (!value) {
    return "Aucune activité";
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <Card className="p-5">
      <p className="text-xs font-bold uppercase tracking-[0.1em] text-[#8190a1]">
        {label}
      </p>
      <p className="mt-3 font-sora text-3xl font-bold text-[#293c52]">{value}</p>
      <p className="mt-2 text-sm text-[#718196]">{detail}</p>
    </Card>
  );
}

export function OrganizerEventLiveDashboardPage() {
  const { eventId } = useParams<{ eventId: string }>();

  const dashboardQuery = useQuery({
    queryKey: ["access", "event", eventId, "live-dashboard"],
    queryFn: () => {
      if (!eventId) {
        throw new Error("EVENT_ID_REQUIRED");
      }

      return fetchEventLiveDashboard(eventId);
    },
    enabled: Boolean(eventId),
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
  });

  const dashboard = dashboardQuery.data;

  return (
    <OrganizerShell
      activeItem="events"
      breadcrumbs={
        <div className="flex items-center gap-2 text-sm">
          <Link to="/organizer/events" className="font-medium text-[#8a96a5] hover:text-[#1769d2]">
            Événements
          </Link>
          <span aria-hidden="true">/</span>
          {eventId ? (
            <Link
              to={`/organizer/events/${eventId}`}
              className="font-medium text-[#8a96a5] hover:text-[#1769d2]"
            >
              Détail
            </Link>
          ) : null}
          <span aria-hidden="true">/</span>
          <span className="font-semibold text-[#34465c]">Dashboard live</span>
        </div>
      }
    >
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[1180px]">
          {dashboardQuery.isPending ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <Spinner label="Chargement du dashboard live" />
            </div>
          ) : dashboardQuery.isError || !dashboard ? (
            <Card className="p-8 text-center">
              Impossible de charger le dashboard live.
            </Card>
          ) : (
            <div className="space-y-5">
              <section className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#1769d2]">
                    Suivi en direct
                  </p>
                  <h1 className="mt-2 font-sora text-3xl font-bold text-[#293c52]">
                    {dashboard.event_name}
                  </h1>
                  <p className="mt-2 text-sm text-[#718196]">
                    Actualisation automatique toutes les 10 secondes · Dernière mise à jour :{" "}
                    {formatDate(dashboard.generated_at)}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    void dashboardQuery.refetch();
                  }}
                  className="min-h-[44px] rounded-xl border border-[#b9cbe0] bg-white px-5 text-sm font-semibold text-[#405b78]"
                >
                  Actualiser
                </button>
              </section>

              <Card
                className={
                  dashboard.admission.is_open
                    ? "border-[#a7dabc] bg-[#f4fff7] p-5"
                    : "border-[#f0d3d3] bg-[#fffafa] p-5"
                }
              >
                <p className="font-semibold text-[#30445b]">
                  {dashboard.admission.is_open ? "Entrées ouvertes" : "Entrées fermées"}
                </p>
                <p className="mt-1 text-sm text-[#66788b]">
                  {dashboard.admission.is_open
                    ? `Ouvertes depuis ${formatDate(dashboard.admission.opened_at)}.`
                    : "Les scanners ne peuvent pas valider de billet."}
                </p>
              </Card>

              <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Metric
                  label="Billets vendus"
                  value={dashboard.ticketing.sold_count}
                  detail={`sur ${dashboard.ticketing.quota_total} places commercialisées`}
                />
                <Metric
                  label="Billets restants"
                  value={dashboard.ticketing.remaining_count}
                  detail="places encore disponibles à la vente"
                />
                <Metric
                  label="Entrées validées"
                  value={dashboard.capacity.entries_count}
                  detail={`${dashboard.capacity.entry_rate_percent}% des billets vendus`}
                />
                <Metric
                  label="Capacité remplie"
                  value={`${dashboard.capacity.capacity_rate_percent}%`}
                  detail={
                    dashboard.capacity.total
                      ? `${dashboard.capacity.entries_count} / ${dashboard.capacity.total} personnes`
                      : "capacité non renseignée"
                  }
                />
              </section>

              <Card className="overflow-hidden p-0">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#edf0f3] p-6">
                  <div>
                    <h2 className="font-sora text-lg font-bold text-[#30445b]">
                      Activité des scanners
                    </h2>
                    <p className="mt-1 text-sm text-[#718196]">
                      {dashboard.scanners.present_count} présent(s) ·{" "}
                      {dashboard.scanners.absent_count} sans signal récent
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-[#405b78]">
                    {dashboard.scanners.assigned_count} scanner(s) affecté(s)
                  </p>
                </div>

                {dashboard.scanners.items.length ? (
                  <div className="divide-y divide-[#edf0f3]">
                    {dashboard.scanners.items.map((scanner) => (
                      <div
                        key={scanner.scanner_id}
                        className="flex flex-wrap items-center justify-between gap-4 px-6 py-4"
                      >
                        <div>
                          <p className="font-semibold text-[#40556b]">{scanner.name}</p>
                          <p className="mt-1 text-xs text-[#8a97a5]">{scanner.email}</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-5 text-sm">
                          <span className="font-semibold text-[#40556b]">
                            {scanner.scan_count} scan(s)
                          </span>
                          <span className="text-[#718196]">
                            Signal : {formatDate(scanner.last_seen_at)}
                          </span>
                          <span className="text-[#718196]">
                            Scan : {formatDate(scanner.last_activity)}
                          </span>
                          <span
                            className={
                              scanner.is_present
                                ? "rounded-full bg-[#daf5e2] px-3 py-1 text-xs font-bold text-[#25733a]"
                                : "rounded-full bg-[#eef1f5] px-3 py-1 text-xs font-bold text-[#657487]"
                            }
                          >
                            {scanner.is_present ? "Présent" : "Absent"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="p-6 text-sm text-[#718196]">
                    Aucun scanner actif n’est affecté à cet événement.
                  </p>
                )}
              </Card>

              {eventId ? (
                <Link
                  to={`/organizer/events/${eventId}`}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[#d6dfe8] bg-white px-5 text-sm font-semibold text-[#536579]"
                >
                  ← Retour à l’événement
                </Link>
              ) : null}
            </div>
          )}
        </div>
      </main>
    </OrganizerShell>
  );
}
