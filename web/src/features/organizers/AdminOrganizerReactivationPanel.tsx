import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, Modal } from "@/components/primitives";
import { StepUpDialog } from "@/features/auth/StepUpDialog";
import { confirmStepUp, requestStepUp, type StepUpChallenge } from "@/features/auth/stepUp";
import type { AppError } from "@/lib/errors";

import {
  approveAdminOrganizerReactivation,
  fetchAdminOrganizerReactivationRequest,
  organizerReactivationQueryKeys,
  rejectAdminOrganizerReactivation,
} from "./reactivation";
import type { Organizer } from "./types";
import { organizerQueryKeys } from "./useOrganizers";

interface AdminOrganizerReactivationPanelProps {
  organizer: Organizer;
}

type Decision =
  | {
      kind: "approve";
    }
  | {
      kind: "reject";
      reason: string;
    };

interface PendingStepUp {
  challenge: StepUpChallenge;
  decision: Decision;
}

function errorMessage(error: unknown): string {
  const appError = error as AppError;

  return appError.message || "Impossible de traiter la demande de réouverture. Réessayez.";
}

export function AdminOrganizerReactivationPanel({
  organizer,
}: AdminOrganizerReactivationPanelProps) {
  const queryClient = useQueryClient();

  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [stepUp, setStepUp] = useState<PendingStepUp | null>(null);
  const [stepUpError, setStepUpError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: organizerReactivationQueryKeys.admin(organizer.id),
    queryFn: () => fetchAdminOrganizerReactivationRequest(organizer.id),
    enabled: organizer.validation_status === "SUSPENDED",
    retry: false,
  });

  if (organizer.validation_status !== "SUSPENDED") {
    return null;
  }

  const reactivationRequest = query.data?.request ?? null;
  const pending = reactivationRequest?.status === "PENDING";

  async function refreshAfterDecision(): Promise<void> {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: organizerReactivationQueryKeys.admin(organizer.id),
      }),
      queryClient.invalidateQueries({
        queryKey: organizerQueryKeys.detail(organizer.id),
      }),
      queryClient.invalidateQueries({
        queryKey: organizerQueryKeys.lists(),
      }),
    ]);
  }

  async function executeDecision(decision: Decision): Promise<void> {
    if (decision.kind === "approve") {
      await approveAdminOrganizerReactivation(organizer.id, organizer.version);

      return;
    }

    await rejectAdminOrganizerReactivation(organizer.id, organizer.version, decision.reason);
  }

  async function completeDecision(decision: Decision): Promise<void> {
    setDialog(null);
    setRejectReason("");
    setActionError(null);

    setFeedback(
      decision.kind === "approve" ? "Réouverture approuvée." : "Demande de réouverture refusée.",
    );

    await refreshAfterDecision();
  }

  async function runDecision(decision: Decision): Promise<void> {
    if (isSubmitting) return;

    setIsSubmitting(true);
    setActionError(null);
    setFeedback(null);

    try {
      await executeDecision(decision);
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
          setDialog(null);
        } catch (stepUpRequestError) {
          setActionError(errorMessage(stepUpRequestError));
        }
      } else {
        setActionError(errorMessage(error));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function confirmPendingStepUp(code: string): Promise<boolean> {
    if (!stepUp) return true;

    setStepUpError(null);

    try {
      await confirmStepUp(stepUp.challenge.challenge_id, code);
    } catch (error) {
      setStepUpError(errorMessage(error));
      return false;
    }

    try {
      await executeDecision(stepUp.decision);
      await completeDecision(stepUp.decision);
      setStepUp(null);

      return true;
    } catch (error) {
      setStepUp(null);
      setActionError(errorMessage(error));

      return true;
    }
  }

  function closeStepUp() {
    if (isSubmitting) return;

    setStepUp(null);
    setStepUpError(null);
  }

  return (
    <section
      aria-labelledby="organizer-reactivation-admin-title"
      className="mx-auto w-full max-w-4xl px-6 pb-8 md:px-8"
    >
      <Card className="border-primary/15 p-6">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">Réactivation</p>

        <h2
          id="organizer-reactivation-admin-title"
          className="mt-2 font-sora text-xl font-bold text-navy"
        >
          Demande de réouverture
        </h2>

        <p className="mt-3 text-sm leading-6 text-navy/65">
          Le compte reste suspendu tant qu’un administrateur n’a pas validé sa réouverture.
        </p>

        {query.isPending ? (
          <p role="status" className="mt-4 text-sm text-navy/55">
            Chargement de la demande de réouverture…
          </p>
        ) : null}

        {query.isError ? (
          <div className="mt-4">
            <p role="alert" className="text-sm text-red-700">
              Impossible de charger la demande de réouverture.
            </p>

            <Button
              type="button"
              className="mt-3"
              onClick={() => {
                void query.refetch();
              }}
            >
              Réessayer
            </Button>
          </div>
        ) : null}

        {!query.isPending && !query.isError && !reactivationRequest ? (
          <div className="mt-4 rounded-xl border border-navy/10 bg-navy/[0.03] p-4">
            <p className="text-sm text-navy/60">
              Aucune demande de réouverture n’a encore été envoyée par cet organisateur.
            </p>
          </div>
        ) : null}

        {reactivationRequest ? (
          <div className="mt-4 rounded-xl border border-navy/10 bg-white p-4">
            <p className="text-sm font-semibold text-navy">
              Statut de la demande :{" "}
              {reactivationRequest.status === "PENDING"
                ? "En attente"
                : reactivationRequest.status === "APPROVED"
                  ? "Approuvée"
                  : "Refusée"}
            </p>

            <p className="mt-2 text-xs text-navy/50">
              Identifiant de traçabilité : {reactivationRequest.id}
            </p>

            {reactivationRequest.status === "REJECTED" && reactivationRequest.rejection_reason ? (
              <p className="mt-3 text-sm text-red-700">
                Motif : {reactivationRequest.rejection_reason}
              </p>
            ) : null}
          </div>
        ) : null}

        {pending ? (
          <>
            <div className="mt-5 rounded-xl border border-primary/20 bg-primary/5 p-4">
              <p className="text-sm font-semibold text-navy">Décision administrative requise</p>

              <p className="mt-2 text-sm leading-6 text-navy/60">
                L’acceptation déclenche une vérification OTP administrateur. Le code de vérification
                est valable 5 minutes.
              </p>
            </div>

            <div className="mt-5 flex flex-wrap gap-3">
              <Button
                type="button"
                disabled={isSubmitting}
                onClick={() => {
                  setActionError(null);
                  setDialog("approve");
                }}
              >
                Approuver la réouverture
              </Button>

              <Button
                type="button"
                disabled={isSubmitting}
                className="bg-navy"
                onClick={() => {
                  setActionError(null);
                  setDialog("reject");
                }}
              >
                Refuser la réouverture
              </Button>
            </div>
          </>
        ) : null}

        {feedback ? (
          <p
            role="status"
            className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm font-medium text-emerald-800"
          >
            {feedback}
          </p>
        ) : null}

        {actionError ? (
          <p role="alert" className="mt-4 text-sm text-red-700">
            {actionError}
          </p>
        ) : null}
      </Card>

      <Modal
        open={dialog === "approve"}
        onClose={() => {
          if (!isSubmitting) setDialog(null);
        }}
        title="Approuver la réouverture"
      >
        <p className="text-sm leading-6 text-navy/70">
          Vous allez autoriser la réactivation de « {organizer.org_name} ». Seul un administrateur
          peut effectuer cette action.
        </p>

        <p className="mt-3 text-sm leading-6 text-navy/60">
          Une vérification OTP administrateur sera exigée. Le code expire après 5 minutes.
        </p>

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button
            type="button"
            className="bg-navy"
            disabled={isSubmitting}
            onClick={() => setDialog(null)}
          >
            Annuler
          </Button>

          <Button
            type="button"
            disabled={isSubmitting}
            onClick={() => {
              void runDecision({
                kind: "approve",
              });
            }}
          >
            {isSubmitting ? "Validation…" : "Confirmer la réouverture"}
          </Button>
        </div>
      </Modal>

      <Modal
        open={dialog === "reject"}
        onClose={() => {
          if (!isSubmitting) setDialog(null);
        }}
        title="Refuser la réouverture"
      >
        <label htmlFor="reactivation-reject-reason" className="block text-sm font-medium text-navy">
          Motif du refus
        </label>

        <textarea
          id="reactivation-reject-reason"
          value={rejectReason}
          disabled={isSubmitting}
          rows={5}
          maxLength={2000}
          className="mt-2 w-full rounded-xl border border-navy/15 bg-white px-4 py-3 text-sm text-navy outline-none transition focus:border-primary"
          onChange={(event) => {
            setRejectReason(event.target.value);
          }}
        />

        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <Button
            type="button"
            className="bg-navy"
            disabled={isSubmitting}
            onClick={() => setDialog(null)}
          >
            Annuler
          </Button>

          <Button
            type="button"
            disabled={isSubmitting || rejectReason.trim().length === 0}
            onClick={() => {
              const reason = rejectReason.trim();

              if (!reason) return;

              void runDecision({
                kind: "reject",
                reason,
              });
            }}
          >
            {isSubmitting ? "Refus…" : "Confirmer le refus"}
          </Button>
        </div>
      </Modal>

      <StepUpDialog
        open={stepUp !== null}
        expiresInSeconds={stepUp?.challenge.expires_in_seconds ?? 300}
        error={stepUpError}
        onClose={closeStepUp}
        onConfirm={confirmPendingStepUp}
      />
    </section>
  );
}
