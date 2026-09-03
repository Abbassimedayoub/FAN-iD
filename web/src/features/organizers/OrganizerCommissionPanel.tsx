import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button, Card, Input } from "@/components/primitives";
import type { AppError } from "@/lib/errors";

import {
  acceptMyCommissionProposal,
  commissionPercentToRate,
  createMyCommissionProposal,
  formatCommissionDate,
  formatCommissionRate,
  organizerCommissionQueryKeys,
  type OrganizerCommissionNegotiation,
} from "./commission";
import { myOrganizerQueryKey } from "./myOrganizer";
import type { Organizer } from "./types";

interface OrganizerCommissionPanelProps {
  organizer: Organizer;
  negotiation: OrganizerCommissionNegotiation | undefined;
  isPending: boolean;
  isError: boolean;
  onRetry: () => void;
}

function actionErrorMessage(error: unknown): string {
  const appError = error as Partial<AppError>;

  if (appError.code === "STALE_RESOURCE") {
    return "La négociation a changé depuis son dernier chargement. Rechargez-la avant de réessayer.";
  }

  return appError.message || "Impossible de mettre à jour la négociation. Réessayez.";
}

export function OrganizerCommissionPanel({
  organizer,
  negotiation,
  isPending,
  isError,
  onRetry,
}: OrganizerCommissionPanelProps) {
  const queryClient = useQueryClient();
  const [counterPercent, setCounterPercent] = useState("");
  const [actionPending, setActionPending] = useState<"counter" | "accept" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  if (isPending) {
    return (
      <Card className="mb-6 p-6">
        <p role="status" className="text-sm text-navy/55">
          Chargement de la négociation de commission…
        </p>
      </Card>
    );
  }

  if (isError || !negotiation) {
    return (
      <Card className="mb-6 p-6">
        <h2 className="font-sora text-xl font-bold text-navy">Commission FANID</h2>

        <p role="alert" className="mt-3 text-sm text-red-700">
          Impossible de charger la négociation de commission.
        </p>

        <Button type="button" className="mt-4" onClick={onRetry}>
          Réessayer
        </Button>
      </Card>
    );
  }

  const negotiationVersion = negotiation.version;
  const proposals = negotiation.proposals ?? [];
  const latestProposal = proposals.length > 0 ? proposals[proposals.length - 1] : null;

  const canRespond =
    negotiation.commission_status === "NEGOTIATING" &&
    (negotiation.validation_status === "PENDING" || negotiation.validation_status === "APPROVED") &&
    latestProposal?.proposer_role === "ADMIN";

  function applyNegotiation(next: OrganizerCommissionNegotiation): void {
    queryClient.setQueryData(organizerCommissionQueryKeys.my, next);

    queryClient.setQueryData<Organizer>(myOrganizerQueryKey, (current) => {
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
      queryKey: myOrganizerQueryKey,
    });
  }

  async function sendCounterProposal(): Promise<void> {
    if (!canRespond || actionPending) {
      return;
    }

    let rate: string;

    try {
      rate = commissionPercentToRate(counterPercent);
    } catch {
      setActionError("Saisissez un pourcentage compris entre 0 et 100.");
      return;
    }

    setActionPending("counter");
    setActionError(null);
    setFeedback(null);

    try {
      const next = await createMyCommissionProposal(negotiationVersion, rate);
      applyNegotiation(next);
      setCounterPercent("");
      setFeedback("Votre contre-proposition a été envoyée à FANID.");
    } catch (error) {
      setActionError(actionErrorMessage(error));
    } finally {
      setActionPending(null);
    }
  }

  async function acceptProposal(): Promise<void> {
    if (!canRespond || actionPending || !latestProposal) {
      return;
    }

    setActionPending("accept");
    setActionError(null);
    setFeedback(null);

    try {
      const next = await acceptMyCommissionProposal(negotiationVersion);
      applyNegotiation(next);
      setFeedback(
        `Commission acceptée : ${formatCommissionRate(next.agreed_rate)}. Votre compte est approuvé automatiquement.`,
      );
    } catch (error) {
      setActionError(actionErrorMessage(error));
    } finally {
      setActionPending(null);
    }
  }

  return (
    <Card className="mb-6 border-primary/15 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">
            Commission FANID
          </p>

          <h2 className="mt-2 font-sora text-xl font-bold text-navy">Négociation de commission</h2>
        </div>

        <span className="rounded-full bg-navy/5 px-3 py-1 text-xs font-semibold text-navy/65">
          {negotiation.commission_status === "COMMISSION_AGREED"
            ? "Accord conclu"
            : negotiation.commission_status === "CANCELLED"
              ? "Négociation annulée"
              : "En négociation"}
        </span>
      </div>

      {negotiation.commission_status === "COMMISSION_AGREED" ? (
        <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <p className="text-sm font-semibold text-emerald-900">
            Commission convenue : {formatCommissionRate(negotiation.agreed_rate)}
          </p>
          <p className="mt-1 text-xs text-emerald-800">
            Accord enregistré le {formatCommissionDate(negotiation.agreed_at)}.
          </p>
        </div>
      ) : null}

      {negotiation.commission_status === "CANCELLED" ? (
        <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-5">
          <p className="text-sm font-semibold text-red-800">
            La négociation est terminée car le dossier organisateur a été rejeté.
          </p>
        </div>
      ) : null}

      {negotiation.commission_status === "NEGOTIATING" ? (
        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <p className="text-sm font-semibold text-amber-900">
            L’accord financier n’est pas encore conclu.
          </p>

          <p className="mt-2 text-sm leading-6 text-amber-800">
            Votre dossier reste en attente pendant la négociation. Dès qu’un accord est accepté,
            votre compte est approuvé automatiquement et l’accès commercial est débloqué.
          </p>
        </div>
      ) : null}

      <div className="mt-6">
        <h3 className="text-sm font-bold text-navy">Historique des propositions</h3>

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
                    {proposal.proposer_role === "ORGANIZER" ? "Vous" : "FANID"}
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
            FANID propose {formatCommissionRate(latestProposal.rate)}.
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,220px)_1fr]">
            <div>
              <label
                htmlFor="organizer-commission-counter"
                className="mb-2 block text-sm font-medium text-navy"
              >
                Votre contre-proposition (%)
              </label>

              <Input
                id="organizer-commission-counter"
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={counterPercent}
                disabled={actionPending !== null}
                onChange={(event) => setCounterPercent(event.target.value)}
                className="w-full"
              />
            </div>

            <div className="flex flex-wrap items-end gap-3">
              <Button
                type="button"
                disabled={actionPending !== null || counterPercent.trim().length === 0}
                onClick={() => {
                  void sendCounterProposal();
                }}
              >
                {actionPending === "counter" ? "Envoi…" : "Envoyer ma contre-proposition"}
              </Button>

              <Button
                type="button"
                disabled={actionPending !== null}
                className="bg-emerald-700"
                onClick={() => {
                  void acceptProposal();
                }}
              >
                {actionPending === "accept"
                  ? "Acceptation…"
                  : `Accepter ${formatCommissionRate(latestProposal.rate)}`}
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {negotiation.commission_status === "NEGOTIATING" &&
      latestProposal?.proposer_role === "ORGANIZER" ? (
        <p className="mt-6 rounded-xl bg-navy/[0.035] px-4 py-3 text-sm text-navy/60">
          Votre proposition est en attente de la réponse de FANID.
        </p>
      ) : null}

      {feedback ? <p className="mt-4 text-sm font-semibold text-emerald-700">{feedback}</p> : null}

      {actionError ? (
        <p role="alert" className="mt-4 text-sm font-medium text-red-700">
          {actionError}
        </p>
      ) : null}

      <p className="mt-5 text-xs text-navy/40">
        Dossier {organizer.org_name} · version de négociation {negotiation.version}
      </p>
    </Card>
  );
}
