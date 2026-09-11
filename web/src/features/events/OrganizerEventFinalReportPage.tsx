import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { Card, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";

import { fetchEventFinalReport } from "./api";

function money(cents: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(cents / 100);
}

function dateTime(value: string | null): string {
  if (!value) {
    return "—";
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function OrganizerEventFinalReportPage() {
  const { eventId } = useParams<{ eventId: string }>();

  const reportQuery = useQuery({
    queryKey: ["access", "event", eventId, "final-report"],
    queryFn: () => {
      if (!eventId) {
        throw new Error("EVENT_ID_REQUIRED");
      }

      return fetchEventFinalReport(eventId);
    },
    enabled: Boolean(eventId),
  });

  const report = reportQuery.data;

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
          <span className="font-semibold text-[#34465c]">Rapport final</span>
        </div>
      }
    >
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[980px]">
          {reportQuery.isPending ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <Spinner label="Chargement du rapport final" />
            </div>
          ) : reportQuery.isError || !report ? (
            <Card className="p-8 text-center">
              <h1 className="font-sora text-xl font-bold text-[#30445b]">
                Rapport final indisponible
              </h1>
              <p className="mt-3 text-sm text-[#66788b]">
                Il sera disponible lorsque l’événement aura été clôturé.
              </p>
            </Card>
          ) : (
            <div className="space-y-5">
              <Card className="p-6 sm:p-8">
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#1769d2]">
                  Événement terminé
                </p>
                <h1 className="mt-2 font-sora text-3xl font-bold text-[#293c52]">Rapport final</h1>
                <p className="mt-3 text-sm text-[#66788b]">
                  Généré le {dateTime(report.generated_at)}. Le PDF identique a été envoyé par
                  e-mail.
                </p>
              </Card>

              <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  ["Billets vendus", report.tickets.sold_count],
                  ["Billets utilisés", report.tickets.used_count],
                  ["Absents / no-show", report.tickets.absent_count],
                  ["Billets annulés", report.tickets.voided_count],
                ].map(([label, value]) => (
                  <Card key={String(label)} className="p-5">
                    <p className="text-xs font-bold uppercase tracking-[0.08em] text-[#8a97a5]">
                      {label}
                    </p>
                    <p className="mt-3 font-sora text-3xl font-bold text-[#30445b]">{value}</p>
                  </Card>
                ))}
              </section>

              <Card className="p-6 sm:p-8">
                <h2 className="font-sora text-lg font-bold text-[#30445b]">Synthèse financière</h2>
                <dl className="mt-5 divide-y divide-[#edf0f3]">
                  {[
                    ["Chiffre d’affaires brut", money(report.financials.gross_revenue_cents)],
                    ["Remboursements", money(report.financials.refunds_cents)],
                    ["Chiffre d’affaires net", money(report.financials.net_revenue_cents)],
                    ["Commission FANID", money(report.financials.commission_cents)],
                    ["Net Organizer", money(report.financials.organizer_net_cents)],
                  ].map(([label, value]) => (
                    <div key={label} className="flex items-center justify-between gap-5 py-4">
                      <dt className="text-sm text-[#66788b]">{label}</dt>
                      <dd className="font-bold text-[#30445b]">{value}</dd>
                    </div>
                  ))}
                </dl>
              </Card>

              <Card className="p-6 sm:p-8">
                <h2 className="font-sora text-lg font-bold text-[#30445b]">Scans par Scanner</h2>
                {report.scanners.length ? (
                  <div className="mt-5 divide-y divide-[#edf0f3]">
                    {report.scanners.map((scanner) => (
                      <div
                        key={scanner.scanner_id}
                        className="flex flex-wrap items-center justify-between gap-3 py-4"
                      >
                        <div>
                          <p className="font-semibold text-[#40556b]">{scanner.name}</p>
                          <p className="mt-1 text-xs text-[#8a97a5]">
                            {scanner.email} · Dernier scan : {dateTime(scanner.last_scan_at)}
                          </p>
                        </div>
                        <p className="font-bold text-[#1769d2]">{scanner.scan_count} scan(s)</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-[#8793a1]">
                    Aucun scan enregistré pour cet événement.
                  </p>
                )}
              </Card>
            </div>
          )}

          <Link
            to={eventId ? `/organizer/events/${eventId}` : "/organizer/events"}
            className="mt-6 inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[#d6dfe8] bg-white px-5 text-sm font-semibold text-[#536579]"
          >
            ← Retour à l’événement
          </Link>
        </div>
      </main>
    </OrganizerShell>
  );
}
