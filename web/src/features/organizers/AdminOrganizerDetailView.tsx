import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import { Button, Card } from "@/components/primitives";
import type { AppError } from "@/lib/errors";

import { OrganizerStatusBadge } from "./OrganizerStatusBadge";
import type { Organizer } from "./types";

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "medium",
  timeStyle: "short",
});

function displayValue(value: string | null): string {
  return value && value.trim().length > 0 ? value : "—";
}

function displayDate(value: string | null): string {
  return value ? DATE_TIME_FORMATTER.format(new Date(value)) : "—";
}

function displayCommission(value: string): string {
  const rate = Number(value);

  if (!Number.isFinite(rate)) {
    return value;
  }

  return `${new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
  }).format(rate * 100)} %`;
}

function DetailSkeleton() {
  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-6 md:p-8">
      <Skeleton className="h-8 w-72" aria-label="Chargement du dossier organisateur" />

      <Card className="flex flex-col gap-5">
        <Skeleton className="h-6 w-56" />
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-2/3" />
      </Card>
    </main>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm font-medium text-navy/60">{label}</dt>
      <dd className="mt-1 text-sm text-navy">{value}</dd>
    </div>
  );
}

interface AdminOrganizerDetailViewProps {
  data: Organizer | undefined;
  isPending: boolean;
  isFetching: boolean;
  error: AppError | null;
  onRetry: () => void;
  onBack: () => void;
}

export function AdminOrganizerDetailView({
  data,
  isPending,
  isFetching,
  error,
  onRetry,
  onBack,
}: AdminOrganizerDetailViewProps) {
  if (isPending) {
    return <DetailSkeleton />;
  }

  if (error?.httpStatus === 404 && !data) {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-6 md:p-8">
        <Button type="button" onClick={onBack} className="self-start">
          Retour aux demandes
        </Button>

        <div role="alert" className="py-12 text-center">
          <h1 className="font-sora text-2xl font-bold text-navy">Cette demande n’existe plus</h1>
          <p className="mt-2 text-sm text-navy/70">
            Elle a peut-être été supprimée ou n’est plus accessible.
          </p>
        </div>
      </main>
    );
  }

  if (error && !data) {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-6 md:p-8">
        <Button type="button" onClick={onBack} className="self-start">
          Retour aux demandes
        </Button>

        <ErrorState error={error} onRetry={onRetry} />
      </main>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-6 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Button type="button" onClick={onBack}>
          Retour aux demandes
        </Button>

        {isFetching ? (
          <p role="status" className="text-sm text-navy/60">
            Actualisation du dossier…
          </p>
        ) : null}
      </div>

      {error ? <ErrorState error={error} onRetry={onRetry} /> : null}

      <header>
        <h1 className="font-sora text-2xl font-bold text-navy">{data.org_name}</h1>
        <div className="mt-3">
          <OrganizerStatusBadge status={data.validation_status} />
        </div>
      </header>

      <Card>
        <dl className="grid gap-5 sm:grid-cols-2">
          <DetailField label="Contact" value={data.contact_email} />
          <DetailField label="N° TVA" value={displayValue(data.vat_number)} />
          <DetailField label="Commission" value={displayCommission(data.commission_rate)} />
          <DetailField label="Déposée le" value={displayDate(data.created_at)} />
          <DetailField label="Validée le" value={displayDate(data.validated_at)} />
          <DetailField label="Motif de rejet" value={displayValue(data.rejection_reason)} />
        </dl>
      </Card>
    </main>
  );
}
