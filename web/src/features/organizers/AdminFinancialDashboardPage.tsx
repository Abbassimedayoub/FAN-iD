import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { fetchAdminFinancialDashboard } from "./api";

const euro = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
});

function money(cents: number): string {
  return euro.format(cents / 100);
}

export function AdminFinancialDashboardPage() {
  const dashboard = useQuery({
    queryKey: ["admin", "financial-dashboard"],
    queryFn: fetchAdminFinancialDashboard,
  });

  if (dashboard.isPending) {
    return <main className="mx-auto max-w-[1500px] p-6 sm:p-8">Chargement du tableau de bord…</main>;
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <main className="mx-auto max-w-[1500px] p-6 sm:p-8">
        <p role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-4 text-red-800">
          Impossible de charger les données financières. Réessayez.
        </p>
      </main>
    );
  }

  const { confirmed_commission_cents: commission, organizer_count: organizerCount, organizers } =
    dashboard.data;

  return (
    <main className="mx-auto max-w-[1500px] p-6 sm:p-8">
      <div className="mb-8">
        <p className="text-sm font-semibold uppercase tracking-wide text-primary">Administration</p>
        <h1 className="mt-2 font-sora text-3xl font-bold text-navy">Accueil FANID</h1>
        <p className="mt-2 max-w-2xl text-sm text-navy/60">
          Les montants affichés sont confirmés à la clôture des événements et tiennent compte
          des remboursements.
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <article className="rounded-3xl bg-navy p-6 text-white shadow-sm">
          <p className="text-sm font-semibold text-white/70">Commission FANID confirmée</p>
          <p className="mt-3 text-4xl font-bold">{money(commission)}</p>
          <p className="mt-3 text-sm text-white/65">Sur les rapports finaux disponibles.</p>
        </article>
        <article className="rounded-3xl border border-[#dce6ef] bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-navy/60">Organizers contributeurs</p>
          <p className="mt-3 text-4xl font-bold text-navy">{organizerCount}</p>
          <Link className="mt-4 inline-flex text-sm font-semibold text-primary hover:underline" to="/admin/organizers">
            Voir tous les Organizers
          </Link>
        </article>
      </section>

      <section className="mt-8 overflow-hidden rounded-3xl border border-[#dce6ef] bg-white shadow-sm">
        <div className="border-b border-[#e7edf3] p-6">
          <h2 className="font-sora text-xl font-bold text-navy">CA net généré par Organizer</h2>
          <p className="mt-1 text-sm text-navy/60">Après remboursements, événements finalisés uniquement.</p>
        </div>

        {organizers.length === 0 ? (
          <p className="p-6 text-sm text-navy/60">Aucun rapport final disponible pour le moment.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-[#f6f8fb] text-navy/60">
                <tr>
                  <th className="px-6 py-4 font-semibold">Organizer</th>
                  <th className="px-6 py-4 font-semibold">Événements finalisés</th>
                  <th className="px-6 py-4 text-right font-semibold">CA net généré</th>
                </tr>
              </thead>
              <tbody>
                {organizers.map((organizer) => (
                  <tr key={organizer.organizer_id} className="border-t border-[#eef2f6]">
                    <td className="px-6 py-4 font-semibold text-navy">{organizer.org_name}</td>
                    <td className="px-6 py-4 text-navy/70">{organizer.completed_events_count}</td>
                    <td className="px-6 py-4 text-right font-bold text-navy">
                      {money(organizer.net_revenue_cents)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
