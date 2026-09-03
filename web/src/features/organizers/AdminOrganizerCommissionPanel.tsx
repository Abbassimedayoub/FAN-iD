import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, Input } from "@/components/primitives";
import { StepUpDialog } from "@/features/auth/StepUpDialog";
import { confirmStepUp, requestStepUp, type StepUpChallenge } from "@/features/auth/stepUp";
import type { AppError } from "@/lib/errors";

import {
  acceptAdminCommissionProposal,
  commissionPercentToRate,
  createAdminCommissionProposal,
  fetchAdminCommissionNegotiation,
  formatCommissionDate,
  formatCommissionRate,
  organizerCommissionQueryKeys,
  type OrganizerCommissionNegotiation,
} from "./commission";
import type { Organizer } from "./types";
import { organizerQueryKeys } from "./useOrganizers";

interface AdminOrganizerCommissionPanelProps {
  organizer: Organizer;
}

type CommissionDecision =
  | {
      kind: "counter";
      version: number;
      rate: string;
    }
  | {
      kind: "accept";
      version: number;
    };

interface PendingStepUp {
  challenge: StepUpChallenge;
  decision: CommissionDecision;
}

function errorMessage(error: unknown): string {
  const appError = error as Partial<AppError>;

  if (appError.code === "STALE_RESOURCE") {
    return "La négociation a été modifiée ailleurs. Rechargez-la avant de réessayer.";
  }

  return appError.message || "Impossible de traiter la négociation de commission.";
}

export function AdminOrganizerCommissionPanel({ organizer }: AdminOrganizerCommissionPanelProps) {
  const queryClient = useQueryClient();
  const [counterPercent, setCounterPercent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState<PendingStepUp | null>(null);
  const [stepUpError, setStepUpError] = useState<string | null>(null);

  const query = useQuery<OrganizerCommissionNegotiation, AppError>({
    queryKey: organizerCommissionQueryKeys.admin(organizer.id),
    queryFn: () => fetchAdminCommissionNegotiation(organizer.id),
    retry: false,
  });

  const negotiation = query.data;
  const proposals = negotiation?.proposals ?? [];
  const latestProposal = proposals.length > 0 ? proposals[proposals.length - 1] : null;

  const canRespond =
    negotiation?.commission_status === "NEGOTIATING" &&
    (negotiation.validation_status === "PENDING" || negotiation.validation_status === "APPROVED") &&
    latestProposal?.proposer_role === "ORGANIZER";

  async function executeDecision(
    decision: CommissionDecision,
  ): Promise<OrganizerCommissionNegotiation> {
    if (decision.kind === "counter") {
      return createAdminCommissionProposal(organizer.id, decision.version, decision.rate);
    }

    return acceptAdminCommissionProposal(organizer.id, decision.version);
  }

  function applyNegotiation(next: OrganizerCommissionNegotiation): void {
    queryClient.setQueryData(organizerCommissionQueryKeys.admin(organizer.id), next);

    queryClient.setQueryData<Organizer>(organizerQueryKeys.detail(organizer.id), (current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        version: next.version,
        validation_status: next.validation_status,
        ...(next.commission_status === "COMMISSION_AGREED" && next.agreed_rate !== null
          ? { commission_rate: next.agreed_rate }
          : {}),
      };
    });

    void queryClient.invalidateQueries({
      queryKey: organizerQueryKeys.detail(organizer.id),
    });

    void queryClient.invalidateQueries({
      queryKey: organizerQueryKeys.lists(),
    });
  }

  async function completeDecision(decision: CommissionDecision): Promise<void> {
    const next = await executeDecision(decision);

    applyNegotiation(next);
    setCounterPercent("");
    setActionError(null);

    setFeedback(
      decision.kind === "accept"
        ? `Commission acceptée : ${formatCommissionRate(next.agreed_rate)}. Compte organisateur approuvé automatiquement.`
        : "Contre-proposition FANID envoyée.",
    );
  }

  async function runDecision(decision: CommissionDecision): Promise<void> {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setActionError(null);
    setFeedback(null);

    try {
      await completeDecision(decision);
    } catch (error) {
      const appError = error as AppError;

      if (appError.code === "STEP_UP_REQUIRED") {
        try {
          const challenge = await requestStepUp();

          setStepUpError(null);
          setStepUp({
            challenge,
            decision,
          });
        } catch (stepUpRequestError) {
          setActionError(errorMessage(stepUpRequestError));
        }
      } else {
        setActionError(errorMessage(error));

        if (appError.code === "STALE_RESOURCE") {
          void query.refetch();
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function sendCounterProposal(): Promise<void> {
    if (!negotiation || !canRespond) {
      return;
    }

    let rate: string;

    try {
      rate = commissionPercentToRate(counterPercent);
    } catch {
      setActionError("Saisissez un pourcentage compris entre 0 et 100.");
      return;
    }

    await runDecision({
      kind: "counter",
      version: negotiation.version,
      rate,
    });
  }

  async function acceptProposal(): Promise<void> {
    if (!negotiation || !canRespond) {
      return;
    }

    await runDecision({
      kind: "accept",
      version: negotiation.version,
    });
  }

  async function confirmPendingStepUp(code: string): Promise<boolean> {
    if (!stepUp) {
      return true;
    }

    setStepUpError(null);

    try {
      await confirmStepUp(stepUp.challenge.challenge_id, code);
    } catch (error) {
      setStepUpError(errorMessage(error));
      return false;
    }

    setIsSubmitting(true);

    try {
      await completeDecision(stepUp.decision);
      setStepUp(null);
      return true;
    } catch (error) {
      const appError = error as AppError;

      setActionError(errorMessage(error));
      setStepUp(null);

      if (appError.code === "STALE_RESOURCE") {
        void query.refetch();
      }

      return true;
    } finally {
      setIsSubmitting(false);
    }
  }

  if (query.isPending) {
    return (
      <Card className="p-6">
        <p role="status" className="text-sm text-navy/55">
          Chargement de la négociation de commission…
        </p>
      </Card>
    );
  }

  if (query.isError || !negotiation) {
    return (
      <Card className="p-6">
        <p role="alert" className="text-sm text-red-700">
          Impossible de charger la négociation de commission.
        </p>

        <Button
          type="button"
          className="mt-4"
          onClick={() => {
            void query.refetch();
          }}
        >
          Réessayer
        </Button>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">
            Accord financier
          </p>

          <h2 className="mt-2 font-sora text-xl font-bold text-navy">Négociation de commission</h2>
        </div>

        <span className="rounded-full bg-navy/5 px-3 py-1 text-xs font-semibold text-navy/65">
          {negotiation.commission_status === "COMMISSION_AGREED"
            ? "Accord conclu"
            : negotiation.commission_status === "CANCELLED"
              ? "Annulée"
              : "En négociation"}
        </span>
      </div>

      <p className="mt-3 text-sm leading-6 text-navy/60">
        Le dossier reste en attente pendant la négociation. Dès qu’un accord de commission est
        accepté, le compte organisateur est approuvé automatiquement.
      </p>

      {negotiation.commission_status === "COMMISSION_AGREED" ? (
        <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-semibold text-emerald-900">
            Commission convenue : {formatCommissionRate(negotiation.agreed_rate)}
          </p>
          <p className="mt-1 text-xs text-emerald-800">
            Accord enregistré le {formatCommissionDate(negotiation.agreed_at)}.
          </p>
        </div>
      ) : null}

      {negotiation.commission_status === "CANCELLED" ? (
        <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-semibold text-red-800">
            Négociation annulée : le dossier organisateur est rejeté.
          </p>
        </div>
      ) : null}

      <div className="mt-6">
        <h3 className="text-sm font-bold text-navy">Historique structuré</h3>

        {proposals.length === 0 ? (
          <p className="mt-3 text-sm text-navy/50">Aucune proposition enregistrée.</p>
        ) : (
          <ol className="mt-3 space-y-3">
            {proposals.map((proposal) => (
              <li
                key={proposal.id}
                className="rounded-xl border border-navy/10 bg-navy/[0.02] px-4 py-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-navy">
                    Proposition #{proposal.sequence} ·{" "}
                    {proposal.proposer_role === "ADMIN" ? "FANID" : "Organisateur"}
                  </p>

                  <p className="text-sm font-bold text-primary">
                    {formatCommissionRate(proposal.rate)}
                  </p>
                </div>

                <p className="mt-1 text-xs text-navy/45">
                  {formatCommissionDate(proposal.created_at)}
                  {proposal.accepted_at
                    ? ` · Acceptée le ${formatCommissionDate(proposal.accepted_at)}`
                    : ""}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>

      {canRespond && latestProposal ? (
        <div className="mt-6 border-t border-navy/10 pt-6">
          <p className="text-sm font-semibold text-navy">
            L’organisateur propose {formatCommissionRate(latestProposal.rate)}.
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,220px)_1fr]">
            <div>
              <label
                htmlFor={`admin-commission-counter-${organizer.id}`}
                className="mb-2 block text-sm font-medium text-navy"
              >
                Contre-proposition FANID (%)
              </label>

              <Input
                id={`admin-commission-counter-${organizer.id}`}
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={counterPercent}
                disabled={isSubmitting}
                onChange={(event) => setCounterPercent(event.target.value)}
                className="w-full"
              />
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <Button
                type="button"
                disabled={isSubmitting || counterPercent.trim().length === 0}
                onClick={() => {
                  void sendCounterProposal();
                }}
              >
                {isSubmitting ? "Traitement…" : "Envoyer la contre-proposition"}
              </Button>

              <Button
                type="button"
                disabled={isSubmitting}
                className="bg-emerald-700"
                onClick={() => {
                  void acceptProposal();
                }}
              >
                {isSubmitting
                  ? "Traitement…"
                  : `Accepter ${formatCommissionRate(latestProposal.rate)}`}
              </Button>
            </div>
          </div>

          <p className="mt-3 text-xs text-navy/45">
            La contre-proposition et l’acceptation sont des actions sensibles protégées par la
            vérification renforcée administrateur.
          </p>
        </div>
      ) : null}

      {negotiation.commission_status === "NEGOTIATING" &&
      latestProposal?.proposer_role === "ADMIN" ? (
        <p className="mt-6 rounded-xl bg-navy/[0.035] px-4 py-3 text-sm text-navy/60">
          La dernière proposition vient de FANID. En attente de la réponse de l’organisateur.
        </p>
      ) : null}

      {feedback ? <p className="mt-4 text-sm font-semibold text-emerald-700">{feedback}</p> : null}

      {actionError ? (
        <p role="alert" className="mt-4 text-sm font-medium text-red-700">
          {actionError}
        </p>
      ) : null}

      {stepUp ? (
        <StepUpDialog
          open
          expiresInSeconds={stepUp.challenge.expires_in_seconds}
          error={stepUpError}
          onClose={() => {
            setStepUp(null);
            setStepUpError(null);
          }}
          onConfirm={confirmPendingStepUp}
        />
      ) : null}
    </Card>
  );
}
