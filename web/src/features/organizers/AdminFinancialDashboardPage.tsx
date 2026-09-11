import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { EmptyState, InlineAlert, Skeleton } from "@/components/primitives";

import { fetchAdminFinancialDashboard } from "./api";

const euro = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
});

function money(cents: number): string {
  return euro.format(cents / 100);
}

function initials(name: string): string {
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part[0]?.toUpperCase())
      .join("")
      .slice(0, 2) || "OR"
  );
}

function DashboardSkeleton() {
  return (
    <main className="fanid-page" aria-label="Chargement de l’accueil administrateur">
      <Skeleton className="h-3 w-28" />
      <Skeleton className="mt-3 h-9 w-64" />
      <Skeleton className="mt-3 h-5 w-full max-w-2xl" />

      <section className="mt-7 grid gap-5 md:grid-cols-3">
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </section>

      <section className="fanid-surface mt-6 overflow-hidden">
        <div className="space-y-3 p-6">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-4 w-96 max-w-full" />
        </div>
        <div className="space-y-4 border-t border-[#edf2f8] p-6">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      </section>
    </main>
  );
}

export function AdminFinancialDashboardPage() {
  const dashboard = useQuery({
    queryKey: ["admin", "financial-dashboard"],
    queryFn: fetchAdminFinancialDashboard,
  });

  if (dashboard.isPending) {
    return <DashboardSkeleton />;
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <main className="fanid-page">
        <p className="fanid-eyebrow">Administration</p>
        <h1 className="fanid-page-title">Accueil FANID</h1>
        <div className="mt-7">
          <InlineAlert tone="danger">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>Impossible de charger les données financières.</span>
              <button
                type="button"
                onClick={() => {
                  void dashboard.refetch();
                }}
                className="min-h-10 rounded-xl border border-red-200 bg-white px-4 text-sm font-bold text-red-800 transition hover:bg-red-50"
              >
                Réessayer
              </button>
            </div>
          </InlineAlert>
        </div>
      </main>
    );
  }

  const {
    confirmed_commission_cents: commission,
    organizer_count: organizerCount,
    organizers,
  } = dashboard.data;
  const completedEventCount = organizers.reduce(
    (total, organizer) => total + organizer.completed_events_count,
    0,
  );

  return (
    <main className="fanid-page">
      <div>
        <p className="fanid-eyebrow">Administration</p>
        <h1 className="fanid-page-title">Accueil FANID</h1>
        <p className="fanid-page-description">
          {" "}
          Les montants affichés sont confirmés à la clôture des événements et tiennent compte des
          remboursements.
        </p>
      </div>

      <section className="mt-7 grid gap-5 md:grid-cols-3" aria-label="Indicateurs financiers">
        <article className="relative overflow-hidden rounded-2xl bg-navy px-6 py-6 text-white shadow-[0_8px_22px_rgba(11,27,46,0.14)]">
          <span className="absolute -right-10 -top-10 h-44 w-44 rounded-full border border-cyan/25" />
          <span className="absolute -right-3 -top-3 h-28 w-28 rounded-full border border-cyan/20" />
          <p className="relative text-[11px] font-bold uppercase tracking-[0.08em] text-cyan">
            Commission FANID confirmée
          </p>
          <p className="relative mt-3 font-sora text-[40px] font-bold leading-none tabular-nums">
            {money(commission)}
          </p>
          <p className="relative mt-4 text-sm leading-6 text-[#aecbe8]">
            Sur les rapports finaux disponibles.
          </p>
        </article>

        <article className="fanid-surface flex min-h-48 flex-col px-6 py-6">
          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#5b6472]">
            Organisateurs contributeurs
          </p>
          <p className="mt-3 font-sora text-[40px] font-bold leading-none text-navy tabular-nums">
            {organizerCount}
          </p>
          <Link
            className="mt-auto pt-5 text-sm font-bold text-primary transition hover:underline"
            to="/admin/organizers"
          >
            Voir tous les organisateurs →{" "}
          </Link>
        </article>

        <article className="fanid-surface flex min-h-48 flex-col px-6 py-6">
          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#5b6472]">
            Événements finalisés
          </p>
          <p className="mt-3 font-sora text-[40px] font-bold leading-none text-navy tabular-nums">
            {completedEventCount}
          </p>
          <p className="mt-auto pt-5 text-sm leading-6 text-[#5b6472]">
            Base de calcul du CA net généré.
          </p>
        </article>
      </section>

      <section className="fanid-surface mt-6 overflow-hidden">
        <div className="border-b border-[#edf2f8] px-6 py-5">
          <h2 className="font-sora text-xl font-bold text-navy">CA net généré par organisateur</h2>
          <p className="mt-1 text-sm leading-6 text-[#5b6472]">
            {" "}
            Après remboursements, événements finalisés uniquement.
          </p>
        </div>

        {organizers.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Aucun rapport final disponible"
              description="Les recettes confirmées apparaîtront ici dès qu’un événement sera clôturé."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-[680px] w-full text-left text-sm">
              <thead className="bg-[#f7fafd] text-[11px] font-bold uppercase tracking-[0.06em] text-[#5b6472]">
                <tr>
                  <th className="px-6 py-3">Organisateur</th>
                  <th className="px-4 py-3">Événements finalisés</th>
                  <th className="px-6 py-3 text-right">CA net généré</th>
                </tr>
              </thead>
              <tbody>
                {organizers.map((organizer) => (
                  <tr
                    key={organizer.organizer_id}
                    className="border-t border-[#edf2f8] transition hover:bg-[#fbfcfe]"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[#eef4fc] text-xs font-bold text-primary">
                          {initials(organizer.org_name)}
                        </span>
                        <span className="font-bold text-navy">{organizer.org_name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-[#3c4b60] tabular-nums">
                      {organizer.completed_events_count}
                    </td>
                    <td className="px-6 py-4 text-right font-bold text-navy tabular-nums">
                      {money(organizer.net_revenue_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-[#e3eaf3] bg-[#fbfcfe]">
                <tr>
                  <td className="px-6 py-3 text-sm text-[#5b6472]">
                    Total · {organizerCount} organisateur{organizerCount > 1 ? "s" : ""}
                  </td>
                  <td className="px-4 py-3 text-sm text-[#5b6472] tabular-nums">
                    {completedEventCount}
                  </td>
                  <td className="px-6 py-3 text-right text-sm font-bold text-navy tabular-nums">
                    {money(
                      organizers.reduce(
                        (total, organizer) => total + organizer.net_revenue_cents,
                        0,
                      ),
                    )}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
