import type { ChangeEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState, getErrorDisplayMessage } from "@/components/ErrorState";
import { RetryButton } from "@/components/RetryButton";
import { Skeleton } from "@/components/Skeleton";
import { Button, Card, Table } from "@/components/primitives";
import type { AppError } from "@/lib/errors";

import { OrganizerTable } from "./OrganizerTable";
import type { OrganizerPage, OrganizerStatus } from "./types";

const PREVIEW_LIMIT = 5;

const FILTER_OPTIONS: readonly {
  value: "" | OrganizerStatus;
  label: string;
}[] = [
  { value: "", label: "Tous les organisateurs" },
  { value: "PENDING", label: "En attente" },
  { value: "APPROVED", label: "Approuvés" },
  { value: "REJECTED", label: "Rejetés" },
  { value: "SUSPENDED", label: "Suspendus" },
];

const STATUS_LABELS: Record<OrganizerStatus, string> = {
  PENDING: "En attente",
  APPROVED: "Approuvés",
  REJECTED: "Rejetés",
  SUSPENDED: "Suspendus",
};

interface AdminOrganizersViewProps {
  validationStatus: OrganizerStatus | undefined;
  displayedValidationStatus: OrganizerStatus | undefined;
  data: OrganizerPage | undefined;
  visiblePage: number;
  isPending: boolean;
  isFetching: boolean;
  error: AppError | null;
  showingPreviousData: boolean;
  showAll?: boolean;
  onValidationStatusChange: (status: OrganizerStatus | undefined) => void;
  onRetry: () => void;
  onShowAll: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onOpenOrganizer?: (organizerId: string) => void;
}

function OrganizerTableSkeleton() {
  return (
    <Table aria-label="Chargement des dossiers organisateurs">
      <thead>
        <tr className="border-b border-navy/10">
          {[
            "Organisateur",
            "Contact",
            "État",
            "N° TVA",
            "Commission",
            "Inscrit le",
            "Validé le",
          ].map((label) => (
            <th key={label} scope="col" className="px-3 py-3">
              {label}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {Array.from({ length: PREVIEW_LIMIT }, (_, index) => (
          <tr
            key={index}
            aria-label={`Chargement de la ligne ${index + 1}`}
            className="border-b border-navy/10"
          >
            {Array.from({ length: 7 }, (_, cell) => (
              <td key={cell} className="px-3 py-4">
                <Skeleton className="h-4 w-24" />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function OrganizerErrorBanner({ error, onRetry }: { error: AppError; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-4"
    >
      <div>
        <p className="font-medium text-navy">{getErrorDisplayMessage(error)}</p>

        <p className="mt-1 text-sm text-navy/60">
          Les dernières données disponibles restent affichées.
        </p>

        {error.correlationId ? (
          <p className="mt-1 text-xs text-navy/40">Référence : {error.correlationId}</p>
        ) : null}
      </div>

      <RetryButton onClick={onRetry} />
    </div>
  );
}

function MetricCard({ label, value, helper }: { label: string; value: number; helper: string }) {
  return (
    <Card className="min-w-0 p-5">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-navy/45">{label}</p>

      <p className="mt-3 font-sora text-3xl font-bold tracking-[-0.04em] text-navy">{value}</p>

      <p className="mt-1 text-xs text-navy/45">{helper}</p>
    </Card>
  );
}

export function AdminOrganizersView({
  validationStatus,
  displayedValidationStatus,
  data,
  visiblePage,
  isPending,
  isFetching,
  error,
  showingPreviousData,
  showAll = false,
  onValidationStatusChange,
  onRetry,
  onShowAll,
  onPrevious,
  onNext,
  onOpenOrganizer,
}: AdminOrganizersViewProps) {
  function handleStatusChange(event: ChangeEvent<HTMLSelectElement>): void {
    const value = event.target.value;

    onValidationStatusChange(value === "" ? undefined : (value as OrganizerStatus));
  }

  const pageCounts: Record<OrganizerStatus, number> = {
    PENDING: 0,
    APPROVED: 0,
    REJECTED: 0,
    SUSPENDED: 0,
  };

  for (const organizer of data?.results ?? []) {
    pageCounts[organizer.validation_status] += 1;
  }

  const activeFilter = displayedValidationStatus
    ? STATUS_LABELS[displayedValidationStatus]
    : "Tous les organisateurs";

  const displayedOrganizers = data
    ? showAll
      ? data.results
      : data.results.slice(0, PREVIEW_LIMIT)
    : [];

  const canShowAll = Boolean(data) && !showAll && (data?.count ?? 0) > PREVIEW_LIMIT;

  return (
    <main className="mx-auto flex w-full max-w-[1400px] flex-col gap-7 p-5 sm:p-6 md:p-8">
      <header>
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">
          Gestion des comptes
        </p>

        <h1 className="font-sora text-2xl font-bold text-navy sm:text-3xl">
          Administration des organisateurs
        </h1>

        <p className="mt-2 max-w-3xl text-sm leading-6 text-navy/70">
          Consultez les organisateurs enregistrés, leur état de validation, leurs informations
          administratives et ouvrez chaque fiche pour effectuer les actions autorisées.
        </p>
      </header>

      {data ? (
        <section aria-labelledby="organizer-overview-title" className="space-y-4">
          <div>
            <h2 id="organizer-overview-title" className="font-sora text-lg font-bold text-navy">
              Vue d’ensemble
            </h2>

            <p className="mt-1 text-xs leading-5 text-navy/45">
              Le total correspond au filtre actif. Les compteurs par état correspondent à la page
              chargée.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <MetricCard
              label="Organisateurs"
              value={data.count}
              helper={`Filtre : ${activeFilter}`}
            />

            <MetricCard label="En attente" value={pageCounts.PENDING} helper="Page chargée" />

            <MetricCard label="Approuvés" value={pageCounts.APPROVED} helper="Page chargée" />

            <MetricCard label="Rejetés" value={pageCounts.REJECTED} helper="Page chargée" />

            <MetricCard label="Suspendus" value={pageCounts.SUSPENDED} helper="Page chargée" />
          </div>
        </section>
      ) : null}

      <section className="space-y-5" aria-labelledby="registered-organizers-title">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 id="registered-organizers-title" className="font-sora text-lg font-bold text-navy">
              Organisateurs enregistrés
            </h2>

            <p className="mt-1 text-sm text-navy/55">
              Les cinq premiers organisateurs sont affichés directement. Ouvrez une fiche pour
              consulter tous ses détails.
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <label className="flex min-w-56 flex-col gap-2 text-sm font-medium text-navy">
              Statut
              <select
                value={validationStatus ?? ""}
                onChange={handleStatusChange}
                className="min-h-[44px] rounded-xl border border-navy/20 bg-white px-3 py-2 outline-none transition focus:border-cyan focus:ring-4 focus:ring-cyan/10"
              >
                {FILTER_OPTIONS.map((option) => (
                  <option key={option.value || "ALL"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            {isFetching && !isPending ? (
              <p role="status" className="pb-3 text-sm text-navy/60">
                Actualisation des dossiers…
              </p>
            ) : null}
          </div>
        </div>

        {isPending ? <OrganizerTableSkeleton /> : null}

        {error && !data ? <ErrorState error={error} onRetry={onRetry} /> : null}

        {error && data ? <OrganizerErrorBanner error={error} onRetry={onRetry} /> : null}

        {data ? (
          data.results.length === 0 ? (
            <EmptyState
              title="Aucun organisateur"
              description="Aucun organisateur ne correspond au filtre sélectionné."
            />
          ) : (
            <>
              <Card className="overflow-hidden p-0">
                <OrganizerTable
                  organizers={displayedOrganizers}
                  onOpenOrganizer={onOpenOrganizer}
                />
              </Card>

              {canShowAll ? (
                <div className="flex justify-center">
                  <Button type="button" onClick={onShowAll}>
                    Voir tous les organisateurs
                  </Button>
                </div>
              ) : null}

              <nav
                aria-label="Pagination des organisateurs"
                className="flex flex-col items-center justify-between gap-4 rounded-2xl border border-[#e4eaf0] bg-white p-4 sm:flex-row"
              >
                <Button
                  type="button"
                  disabled={data.previous === null || isFetching || showingPreviousData}
                  onClick={onPrevious}
                >
                  Précédent
                </Button>

                <p className="text-sm text-navy/70">
                  Page {visiblePage} · {data.count} organisateur
                  {data.count > 1 ? "s" : ""}
                </p>

                <Button
                  type="button"
                  disabled={data.next === null || isFetching || showingPreviousData}
                  onClick={onNext}
                >
                  Suivant
                </Button>
              </nav>
            </>
          )
        ) : null}
      </section>
    </main>
  );
}
