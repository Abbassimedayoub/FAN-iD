import { useEffect, useState } from "react";

import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import { Button, Card, Modal, Toast } from "@/components/primitives";
import { StepUpDialog } from "@/features/auth/StepUpDialog";
import type { AppError } from "@/lib/errors";

import { OrganizerStatusBadge } from "./OrganizerStatusBadge";
import { RejectDialog, SuspendDialog } from "./OrganizerActionDialogs";
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

function DetailSkeleton() {
  return (
    <main className="fanid-page flex max-w-[1140px] flex-col gap-6">
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
      <dt className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#5b6472]">{label}</dt>
      <dd className="mt-1.5 text-sm font-medium text-navy">{value}</dd>
    </div>
  );
}

export interface OrganizerActionFeedback {
  message: string;
  tone: "success" | "danger";
}

export interface OrganizerActionReopen {
  kind: "reject" | "suspend";
  rejectReason?: string;
}

export interface OrganizerStepUpActions {
  expiresInSeconds: number;
  error: string | null;
  onClose: () => void;
  onConfirm: (code: string) => Promise<boolean>;
}

export interface OrganizerDetailActions {
  isPending: boolean;
  feedback: OrganizerActionFeedback | null;
  isStaleResource: boolean;
  onReject: (reason: string) => Promise<boolean>;
  onSuspend: () => Promise<boolean>;
  onReloadStale: () => void;
  onClearReopenAction?: () => void;
  reopenAction?: OrganizerActionReopen | null;
  stepUp?: OrganizerStepUpActions;
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

type ActionDialog = "reject" | "suspend" | null;

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
  const reopenAction = actions?.reopenAction;

  useEffect(() => {
    if (reopenAction) {
      setActionDialog(reopenAction.kind);
    }
  }, [reopenAction]);

  function closeActionDialog() {
    setActionDialog(null);
    actions?.onClearReopenAction?.();
  }

  function openActionDialog(dialog: Exclude<ActionDialog, null>) {
    actions?.onClearReopenAction?.();
    setActionDialog(dialog);
  }

  if (isPending) {
    return <DetailSkeleton />;
  }

  if (error?.httpStatus === 404 && !data) {
    return (
      <main className="fanid-page flex max-w-[1140px] flex-col gap-6">
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
      <main className="fanid-page flex max-w-[1140px] flex-col gap-6">
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
    <main className="fanid-page flex max-w-[1140px] flex-col gap-6">
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

      <header className="flex flex-wrap items-center gap-4">
        <span className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-navy font-sora text-lg font-bold text-cyan">
          {data.org_name
            .split(/\\s+/)
            .filter(Boolean)
            .map((part) => part[0]?.toUpperCase())
            .join("")
            .slice(0, 2) || "OR"}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-sora text-[28px] font-bold leading-tight text-navy">
              {data.org_name}
            </h1>
            <OrganizerStatusBadge status={data.validation_status} />
          </div>
          <p className="mt-1 text-sm leading-6 text-[#5b6472]">
            {data.contact_email} · inscrit le {displayDate(data.created_at)}
            {data.validated_at ? ` · validé le ${displayDate(data.validated_at)}` : ""}
          </p>
        </div>
      </header>

      <Card className="fanid-surface p-6">
        <div className="mb-6">
          <p className="fanid-eyebrow">Dossier organisateur</p>
          <h2 className="mt-1 font-sora text-xl font-bold text-navy">
            Informations administratives
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#5b6472]">
            Données enregistrées pour cet organisateur.
          </p>
        </div>

        <dl className="grid gap-x-7 gap-y-6 sm:grid-cols-2">
          <DetailField label="Contact" value={data.contact_email} />
          <DetailField label="Identifiant du dossier" value={data.id} />
          <DetailField label="N° TVA" value={displayValue(data.vat_number)} />
          <DetailField label="Commission" value="Voir la négociation ci-dessous" />
          <DetailField label="Déposée le" value={displayDate(data.created_at)} />
          <DetailField label="Validée le" value={displayDate(data.validated_at)} />
          <DetailField label="Dernière mise à jour" value={displayDate(data.updated_at)} />
          <DetailField label="Version du dossier" value={String(data.version)} />
          <DetailField label="Motif de rejet" value={displayValue(data.rejection_reason)} />
        </dl>
      </Card>

      {actions && (canReview || canSuspend) ? (
        <Card className="fanid-surface border-[#f3d0d0] p-6">
          <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#b91c1c]">
            Zone sensible
          </p>
          <h2 className="mt-1 font-sora text-xl font-bold text-navy">Actions administratives</h2>
          <p className="mt-2 text-sm leading-6 text-[#5b6472]">
            Ces actions sont tracées et peuvent demander une vérification renforcée.
          </p>

          <div className="mt-5 flex flex-wrap gap-3">
            {canReview ? (
              <Button
                type="button"
                disabled={actions.isPending}
                onClick={() => openActionDialog("reject")}
                className="border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
              >
                Rejeter
              </Button>
            ) : null}

            {canSuspend ? (
              <Button
                type="button"
                disabled={actions.isPending}
                onClick={() => openActionDialog("suspend")}
                className="border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
              >
                Suspendre
              </Button>
            ) : null}
          </div>
        </Card>
      ) : null}

      {actions ? (
        <>
          <RejectDialog
            open={actionDialog === "reject"}
            isPending={actions.isPending}
            initialReason={reopenAction?.kind === "reject" ? reopenAction.rejectReason : undefined}
            onClose={closeActionDialog}
            onConfirm={actions.onReject}
          />

          <SuspendDialog
            open={actionDialog === "suspend"}
            isPending={actions.isPending}
            onClose={closeActionDialog}
            onConfirm={actions.onSuspend}
          />

          {actions.stepUp ? (
            <StepUpDialog
              open
              expiresInSeconds={actions.stepUp.expiresInSeconds}
              error={actions.stepUp.error}
              onClose={actions.stepUp.onClose}
              onConfirm={actions.stepUp.onConfirm}
            />
          ) : null}

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
