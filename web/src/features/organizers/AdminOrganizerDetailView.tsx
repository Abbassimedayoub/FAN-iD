import { useState } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import { Button, Card, Modal, Toast } from "@/components/primitives";
import type { AppError } from "@/lib/errors";

import { OrganizerStatusBadge } from "./OrganizerStatusBadge";
import { ApproveDialog, RejectDialog, SuspendDialog } from "./OrganizerActionDialogs";
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

export interface OrganizerActionFeedback {
  message: string;
  tone: "success" | "danger";
}

export interface OrganizerDetailActions {
  isPending: boolean;
  feedback: OrganizerActionFeedback | null;
  isStaleResource: boolean;
  onApprove: () => Promise<boolean>;
  onReject: (reason: string) => Promise<boolean>;
  onSuspend: () => Promise<boolean>;
  onReloadStale: () => void;
}

interface AdminOrganizerDetailViewProps {
  data: Organizer | undefined;
  isPending: boolean;
  isFetching: boolean;
  error: AppError | null;
  onRetry: () => void;
  onBack: () => void;
  actions?: OrganizerDetailActions;
}

type ActionDialog = "approve" | "reject" | "suspend" | null;

export function AdminOrganizerDetailView({
  data,
  isPending,
  isFetching,
  error,
  onRetry,
  onBack,
  actions,
}: AdminOrganizerDetailViewProps) {
  const [actionDialog, setActionDialog] = useState<ActionDialog>(null);

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

  const canReview = data.validation_status === "PENDING";
  const canSuspend = data.validation_status === "APPROVED";

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

      {actions?.feedback ? (
        <Toast message={actions.feedback.message} tone={actions.feedback.tone} />
      ) : null}

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

      {actions && (canReview || canSuspend) ? (
        <Card>
          <h2 className="font-sora text-lg font-semibold text-navy">Actions administratives</h2>

          <div className="mt-4 flex flex-wrap gap-3">
            {canReview ? (
              <>
                <Button
                  type="button"
                  disabled={actions.isPending}
                  onClick={() => setActionDialog("approve")}
                >
                  Approuver
                </Button>

                <Button
                  type="button"
                  disabled={actions.isPending}
                  onClick={() => setActionDialog("reject")}
                  className="bg-red-600"
                >
                  Rejeter
                </Button>
              </>
            ) : null}

            {canSuspend ? (
              <Button
                type="button"
                disabled={actions.isPending}
                onClick={() => setActionDialog("suspend")}
                className="bg-red-600"
              >
                Suspendre
              </Button>
            ) : null}
          </div>
        </Card>
      ) : null}

      {actions ? (
        <>
          <ApproveDialog
            open={actionDialog === "approve"}
            isPending={actions.isPending}
            onClose={() => setActionDialog(null)}
            onConfirm={actions.onApprove}
          />

          <RejectDialog
            open={actionDialog === "reject"}
            isPending={actions.isPending}
            onClose={() => setActionDialog(null)}
            onConfirm={actions.onReject}
          />

          <SuspendDialog
            open={actionDialog === "suspend"}
            isPending={actions.isPending}
            onClose={() => setActionDialog(null)}
            onConfirm={actions.onSuspend}
          />

          <Modal
            open={actions.isStaleResource}
            onClose={actions.onReloadStale}
            title="Le dossier a changé"
          >
            <p className="text-sm text-navy/70">
              Une autre modification a été enregistrée. Rechargez le dossier avant de réessayer.
            </p>

            <div className="mt-5 flex justify-end">
              <Button type="button" onClick={actions.onReloadStale}>
                Recharger le dossier
              </Button>
            </div>
          </Modal>
        </>
      ) : null}
    </main>
  );
}
