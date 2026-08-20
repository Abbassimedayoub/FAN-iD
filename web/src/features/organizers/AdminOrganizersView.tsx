import type { ChangeEvent } from "react";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState, getErrorDisplayMessage } from "@/components/ErrorState";
import { RetryButton } from "@/components/RetryButton";
import { Skeleton } from "@/components/Skeleton";
import { Button, Table } from "@/components/primitives";
import type { AppError } from "@/lib/errors";

import { OrganizerTable } from "./OrganizerTable";
import type { OrganizerPage, OrganizerStatus } from "./types";

const FILTER_OPTIONS: readonly {
  value: "" | OrganizerStatus;
  label: string;
}[] = [
  { value: "PENDING", label: "En attente" },
  { value: "APPROVED", label: "Approuvés" },
  { value: "REJECTED", label: "Rejetés" },
  { value: "SUSPENDED", label: "Suspendus" },
  { value: "", label: "Toutes les demandes" },
];

interface AdminOrganizersViewProps {
  validationStatus: OrganizerStatus | undefined;
  displayedValidationStatus: OrganizerStatus | undefined;
  data: OrganizerPage | undefined;
  visiblePage: number;
  isPending: boolean;
  isFetching: boolean;
  error: AppError | null;
  showingPreviousData: boolean;
  onValidationStatusChange: (status: OrganizerStatus | undefined) => void;
  onRetry: () => void;
  onShowAll: () => void;
  onPrevious: () => void;
  onNext: () => void;
}

function OrganizerTableSkeleton() {
  return (
    <Table aria-label="Chargement des dossiers organisateurs">
      <thead>
        <tr className="border-b border-navy/10">
          <th scope="col" className="px-3 py-3">
            Organisateur
          </th>
          <th scope="col" className="px-3 py-3">
            Contact
          </th>
          <th scope="col" className="px-3 py-3">
            Statut
          </th>
          <th scope="col" className="px-3 py-3">
            Déposée le
          </th>
        </tr>
      </thead>

      <tbody>
        {Array.from({ length: 5 }, (_, index) => (
          <tr
            key={index}
            aria-label={`Chargement de la ligne ${index + 1}`}
            className="border-b border-navy/10"
          >
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-36" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-44" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-5 w-20" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-24" />
            </td>
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
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 p-4"
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

export function AdminOrganizersView({
  validationStatus,
  displayedValidationStatus,
  data,
  visiblePage,
  isPending,
  isFetching,
  error,
  showingPreviousData,
  onValidationStatusChange,
  onRetry,
  onShowAll,
  onPrevious,
  onNext,
}: AdminOrganizersViewProps) {
  function handleStatusChange(event: ChangeEvent<HTMLSelectElement>): void {
    const value = event.target.value;

    onValidationStatusChange(value === "" ? undefined : (value as OrganizerStatus));
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8">
      <header>
        <h1 className="font-sora text-2xl font-bold text-navy">Administration des organisateurs</h1>
        <p className="mt-2 text-sm text-navy/70">
          Consultez et filtrez les demandes d’activation des organisateurs.
        </p>
      </header>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <label className="flex min-w-56 flex-col gap-2 text-sm font-medium text-navy">
          Statut
          <select
            value={validationStatus ?? ""}
            onChange={handleStatusChange}
            className="min-h-[44px] rounded-md border border-navy/20 bg-white px-3 py-2"
          >
            {FILTER_OPTIONS.map((option) => (
              <option key={option.value || "ALL"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {isFetching && !isPending ? (
          <p role="status" className="text-sm text-navy/60">
            Actualisation des dossiers…
          </p>
        ) : null}
      </div>

      {isPending ? <OrganizerTableSkeleton /> : null}

      {error && !data ? <ErrorState error={error} onRetry={onRetry} /> : null}

      {error && data ? <OrganizerErrorBanner error={error} onRetry={onRetry} /> : null}

      {data ? (
        data.results.length === 0 ? (
          <EmptyState
            title={
              displayedValidationStatus === "PENDING"
                ? "Aucune demande en attente"
                : "Aucune demande"
            }
            description="Aucun dossier ne correspond au filtre sélectionné."
            actionLabel={
              displayedValidationStatus === "PENDING" ? "Voir toutes les demandes" : undefined
            }
            onAction={displayedValidationStatus === "PENDING" ? onShowAll : undefined}
          />
        ) : (
          <>
            <OrganizerTable organizers={data.results} />

            <nav
              aria-label="Pagination des organisateurs"
              className="flex items-center justify-between gap-4"
            >
              <Button
                type="button"
                disabled={data.previous === null || isFetching || showingPreviousData}
                onClick={onPrevious}
              >
                Précédent
              </Button>

              <p className="text-sm text-navy/70">
                Page {visiblePage} · {data.count} dossier
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
    </main>
  );
}
