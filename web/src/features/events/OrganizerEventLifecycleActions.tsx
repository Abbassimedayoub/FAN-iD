import { type FormEvent, useState } from "react";

import { Button, Card, Input, Modal } from "@/components/primitives";
import { toAppError } from "@/lib/errors";

import { cancelEvent, postponeEvent, suspendEvent, unarchiveEvent } from "./api";
import { endDateTimeThreeHoursAfter } from "./eventScheduleDefaults";
import type { OrganizerEvent } from "./types";

type LifecycleDialog = "postpone" | "suspend" | "cancel" | null;

function toDateTimeLocal(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const pad = (number: number): string => String(number).padStart(2, "0");

  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

function toIsoDateTime(value: string): string | null {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return date.toISOString();
}

export function OrganizerEventLifecycleActions({
  event,
  onChanged,
}: {
  event: OrganizerEvent;
  onChanged: (updated: OrganizerEvent) => Promise<void>;
}) {
  const [dialog, setDialog] = useState<LifecycleDialog>(null);

  const [reason, setReason] = useState("");

  const [notifyBuyers, setNotifyBuyers] = useState(true);

  const [refundRequested, setRefundRequested] = useState(true);

  const [postponeStartsAt, setPostponeStartsAt] = useState(toDateTimeLocal(event.starts_at));

  const [postponeEndsAt, setPostponeEndsAt] = useState(toDateTimeLocal(event.ends_at));

  const [pending, setPending] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const isAwaitingNewDate =
    event.status === "POSTPONED" && !event.postponed_to_starts_at && !event.postponed_to_ends_at;

  const canPostpone = event.status === "PUBLISHED" || event.status === "POSTPONED";

  const canSuspend = event.status === "PUBLISHED" || event.status === "POSTPONED";

  const canCancel =
    event.status === "PUBLISHED" || event.status === "POSTPONED" || event.status === "SUSPENDED";

  const canUnarchive = event.status === "ARCHIVED";

  if (!canPostpone && !canSuspend && !canCancel && !canUnarchive) {
    return null;
  }

  function openDialog(nextDialog: Exclude<LifecycleDialog, null>): void {
    setReason("");
    setNotifyBuyers(true);
    setRefundRequested(true);
    setError(null);

    setPostponeStartsAt(toDateTimeLocal(event.starts_at));

    setPostponeEndsAt(toDateTimeLocal(event.ends_at));

    setDialog(nextDialog);
  }

  function closeDialog(): void {
    if (pending) {
      return;
    }

    setDialog(null);
    setError(null);
  }

  function validateReason(): string | null {
    const cleanReason = reason.trim();

    if (!cleanReason) {
      setError("Le motif est obligatoire.");
      return null;
    }

    return cleanReason;
  }

  async function handlePostponeWithoutDate(): Promise<void> {
    const cleanReason = reason.trim();

    if (!cleanReason) {
      setError("Le motif du report est requis.");
      return;
    }

    setPending(true);
    setError(null);

    try {
      const updated = await postponeEvent(event, {
        starts_at: null,
        ends_at: null,
        reason: cleanReason,
        notify_buyers: notifyBuyers,
      });

      await onChanged(updated);
      closeDialog();
    } catch (caught) {
      setError(toAppError(caught).message);
    } finally {
      setPending(false);
    }
  }

  async function handlePostpone(eventForm: FormEvent<HTMLFormElement>): Promise<void> {
    eventForm.preventDefault();

    const lifecycleReason = isAwaitingNewDate ? "" : validateReason();

    if (lifecycleReason === null) {
      return;
    }

    const startsAt = toIsoDateTime(postponeStartsAt);

    const endsAt = toIsoDateTime(postponeEndsAt);

    if (!startsAt || !endsAt) {
      setError("Les nouvelles dates sont invalides.");
      return;
    }

    if (new Date(endsAt) <= new Date(startsAt)) {
      setError("La date de fin doit être postérieure à la date de début.");
      return;
    }

    setPending(true);
    setError(null);

    try {
      const updated = await postponeEvent(event, {
        starts_at: startsAt,
        ends_at: endsAt,
        reason: lifecycleReason,
        notify_buyers: notifyBuyers,
      });

      await onChanged(updated);

      setDialog(null);
    } catch (requestError) {
      setError(toAppError(requestError).message);
    } finally {
      setPending(false);
    }
  }

  async function handleSuspend(eventForm: FormEvent<HTMLFormElement>): Promise<void> {
    eventForm.preventDefault();

    const cleanReason = validateReason();

    if (!cleanReason) {
      return;
    }

    setPending(true);
    setError(null);

    try {
      const updated = await suspendEvent(event, {
        reason: cleanReason,
        notify_buyers: notifyBuyers,
      });

      await onChanged(updated);

      setDialog(null);
    } catch (requestError) {
      setError(toAppError(requestError).message);
    } finally {
      setPending(false);
    }
  }

  async function handleCancel(eventForm: FormEvent<HTMLFormElement>): Promise<void> {
    eventForm.preventDefault();

    const cleanReason = validateReason();

    if (!cleanReason) {
      return;
    }

    setPending(true);
    setError(null);

    try {
      const updated = await cancelEvent(event, {
        reason: cleanReason,
        notify_buyers: notifyBuyers,
        refund_requested: refundRequested,
      });

      await onChanged(updated);

      setDialog(null);
    } catch (requestError) {
      setError(toAppError(requestError).message);
    } finally {
      setPending(false);
    }
  }

  async function handleUnarchive(): Promise<void> {
    setPending(true);
    setError(null);

    try {
      const updated = await unarchiveEvent(event);

      await onChanged(updated);
    } catch (requestError) {
      setError(toAppError(requestError).message);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <Card className="p-6 sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="font-sora text-lg font-bold text-[#30445b]">Gestion de l’événement</h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#7b8998]">
              Gérez les changements importants après publication. Chaque action est historisée et
              protégée contre les modifications concurrentes.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {canPostpone ? (
              <Button
                type="button"
                onClick={() => {
                  openDialog("postpone");
                  if (isAwaitingNewDate) {
                    setPostponeStartsAt("");
                    setPostponeEndsAt("");
                  }
                }}
                className="border border-[#b9d4f6] bg-white font-semibold text-[#1769d2] hover:bg-[#f4f8fe]"
              >
                {isAwaitingNewDate ? "Définir une nouvelle date" : "Reporter"}
              </Button>
            ) : null}

            {canSuspend ? (
              <Button
                type="button"
                onClick={() => {
                  openDialog("suspend");
                }}
                className="border border-amber-200 bg-white font-semibold text-amber-700 hover:bg-amber-50"
              >
                Suspendre
              </Button>
            ) : null}

            {canCancel ? (
              <Button
                type="button"
                onClick={() => {
                  openDialog("cancel");
                }}
                className="border border-red-200 bg-white font-semibold text-red-700 hover:bg-red-50"
              >
                Annuler
              </Button>
            ) : null}

            {canUnarchive ? (
              <Button
                type="button"
                disabled={pending}
                onClick={() => {
                  void handleUnarchive();
                }}
                className="border border-[#b9d4f6] bg-white font-semibold text-[#1769d2] hover:bg-[#f4f8fe]"
              >
                {pending ? "Désarchivage…" : "Désarchiver"}
              </Button>
            ) : null}
          </div>
        </div>

        {canUnarchive && error ? (
          <p role="alert" className="mt-4 text-sm font-medium text-red-600">
            {error}
          </p>
        ) : null}
      </Card>

      <Modal
        open={dialog === "postpone"}
        onClose={closeDialog}
        title={isAwaitingNewDate ? "Définir une nouvelle date" : "Reporter l’événement"}
      >
        <form className="space-y-4" onSubmit={handlePostpone}>
          <p className="text-sm leading-6 text-navy/60">
            {isAwaitingNewDate
              ? "Définissez la nouvelle programmation de l’événement."
              : "Définissez les nouvelles dates et indiquez la raison du report."}
          </p>

          <label htmlFor="postpone-starts-at" className="block">
            <span className="mb-1.5 block text-sm font-semibold text-navy">
              Nouvelle date de début
            </span>

            <Input
              id="postpone-starts-at"
              type="datetime-local"
              value={postponeStartsAt}
              onChange={(changeEvent) => {
                const nextStartsAt = changeEvent.target.value;

                setPostponeStartsAt(nextStartsAt);

                const nextEndsAt = endDateTimeThreeHoursAfter(nextStartsAt);

                if (nextEndsAt) {
                  setPostponeEndsAt(nextEndsAt);
                }
              }}
              required
              className="w-full"
            />
          </label>

          <label htmlFor="postpone-ends-at" className="block">
            <span className="mb-1.5 block text-sm font-semibold text-navy">
              Nouvelle date de fin
            </span>

            <Input
              id="postpone-ends-at"
              type="datetime-local"
              value={postponeEndsAt}
              onChange={(changeEvent) => {
                setPostponeEndsAt(changeEvent.target.value);
              }}
              required
              className="w-full"
            />
          </label>

          {!isAwaitingNewDate ? (
            <label className="block">
              <span className="mb-1.5 block text-sm font-semibold text-navy">Motif du report</span>

              <textarea
                value={reason}
                onChange={(changeEvent) => {
                  setReason(changeEvent.target.value);
                }}
                required
                rows={4}
                className="w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-3 text-sm text-navy outline-none transition focus:border-cyan focus:ring-4 focus:ring-cyan/10"
              />
            </label>
          ) : null}

          <div className="flex cursor-pointer items-start gap-3 rounded-xl bg-[#f7f9fc] p-4">
            <input
              id="postpone-notify-buyers"
              aria-label="Informer les acheteurs du report par e-mail"
              type="checkbox"
              checked={notifyBuyers}
              onChange={(changeEvent) => {
                setNotifyBuyers(changeEvent.target.checked);
              }}
              className="mt-1 h-4 w-4"
            />

            <span>
              <span className="block text-sm font-semibold text-navy">
                Informer les acheteurs par e-mail
              </span>

              <span className="mt-1 block text-xs leading-5 text-navy/50">
                La demande de notification est enregistrée dans l’Outbox. L’envoi aux acheteurs sera
                connecté au module de vente.
              </span>
            </span>
          </div>

          {error ? (
            <p role="alert" className="text-sm font-medium text-red-600">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              disabled={pending}
              onClick={closeDialog}
              className="border border-[#d7e0e9] bg-white font-semibold text-navy hover:bg-slate-50"
            >
              Retour
            </Button>

            <Button type="submit" disabled={pending} className="font-semibold">
              {pending
                ? isAwaitingNewDate
                  ? "Enregistrement…"
                  : "Report…"
                : isAwaitingNewDate
                  ? "Enregistrer la nouvelle date"
                  : "Confirmer le report"}
            </Button>
          </div>
          {!isAwaitingNewDate ? (
            <div className="border-t border-slate-100 pt-4">
              <Button
                type="button"
                disabled={pending}
                onClick={() => {
                  void handlePostponeWithoutDate();
                }}
                className="w-full border border-blue-200 bg-blue-50 font-semibold text-blue-700 hover:bg-blue-100"
              >
                Reporter sans nouvelle date
              </Button>

              <p className="mt-2 text-xs leading-5 text-navy/50">
                L’ancienne programmation sera conservée et les utilisateurs verront « Nouvelle date
                à venir ».
              </p>
            </div>
          ) : null}
        </form>
      </Modal>

      <Modal open={dialog === "suspend"} onClose={closeDialog} title="Suspendre l’événement">
        <form className="space-y-4" onSubmit={handleSuspend}>
          <p className="text-sm leading-6 text-navy/60">
            La suspension est temporaire. Indiquez la raison destinée au suivi opérationnel.
          </p>

          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-navy">
              Motif de la suspension
            </span>

            <textarea
              value={reason}
              onChange={(changeEvent) => {
                setReason(changeEvent.target.value);
              }}
              required
              rows={4}
              className="w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-3 text-sm text-navy outline-none transition focus:border-cyan focus:ring-4 focus:ring-cyan/10"
            />
          </label>

          <div className="flex cursor-pointer items-start gap-3 rounded-xl bg-[#fff9eb] p-4">
            <input
              id="suspend-notify-buyers"
              aria-label="Informer les acheteurs de la suspension par e-mail"
              type="checkbox"
              checked={notifyBuyers}
              onChange={(changeEvent) => {
                setNotifyBuyers(changeEvent.target.checked);
              }}
              className="mt-1 h-4 w-4"
            />

            <span>
              <span className="block text-sm font-semibold text-navy">
                Informer les acheteurs par e-mail
              </span>

              <span className="mt-1 block text-xs leading-5 text-navy/50">
                La demande est conservée pour le futur consommateur de notifications acheteurs.
              </span>
            </span>
          </div>

          {error ? (
            <p role="alert" className="text-sm font-medium text-red-600">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              disabled={pending}
              onClick={closeDialog}
              className="border border-[#d7e0e9] bg-white font-semibold text-navy hover:bg-slate-50"
            >
              Retour
            </Button>

            <Button
              type="submit"
              disabled={pending}
              className="bg-amber-600 font-semibold hover:bg-amber-700"
            >
              {pending ? "Suspension…" : "Confirmer la suspension"}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={dialog === "cancel"} onClose={closeDialog} title="Annuler l’événement">
        <form className="space-y-4" onSubmit={handleCancel}>
          <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm leading-6 text-red-800">
            Cette action est définitive pour le cycle de vie actuel de l’événement.
          </div>

          <label className="block">
            <span className="mb-1.5 block text-sm font-semibold text-navy">
              Motif de l’annulation
            </span>

            <textarea
              value={reason}
              onChange={(changeEvent) => {
                setReason(changeEvent.target.value);
              }}
              required
              rows={4}
              className="w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-3 text-sm text-navy outline-none transition focus:border-cyan focus:ring-4 focus:ring-cyan/10"
            />
          </label>

          <label
            htmlFor="cancel-notify-buyers"
            className="flex cursor-pointer items-start gap-3 rounded-xl bg-[#f7f9fc] p-4"
          >
            <input
              id="cancel-notify-buyers"
              type="checkbox"
              checked={notifyBuyers}
              onChange={(changeEvent) => {
                setNotifyBuyers(changeEvent.target.checked);
              }}
              className="mt-1 h-4 w-4"
            />

            <span className="text-sm font-semibold text-navy">
              Informer les acheteurs par e-mail
            </span>
          </label>

          <div className="flex cursor-pointer items-start gap-3 rounded-xl border border-red-100 bg-red-50 p-4">
            <input
              id="cancel-refund-requested"
              aria-label="Demander le remboursement des acheteurs"
              type="checkbox"
              checked={refundRequested}
              onChange={(changeEvent) => {
                setRefundRequested(changeEvent.target.checked);
              }}
              className="mt-1 h-4 w-4"
            />

            <span>
              <span className="block text-sm font-semibold text-red-800">
                Demander le remboursement des acheteurs
              </span>

              <span className="mt-1 block text-xs leading-5 text-red-700/70">
                La demande est enregistrée maintenant. Le remboursement financier réel sera exécuté
                par le futur module Payments.
              </span>
            </span>
          </div>

          {error ? (
            <p role="alert" className="text-sm font-medium text-red-600">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              disabled={pending}
              onClick={closeDialog}
              className="border border-[#d7e0e9] bg-white font-semibold text-navy hover:bg-slate-50"
            >
              Retour
            </Button>

            <Button
              type="submit"
              disabled={pending}
              className="bg-red-600 font-semibold hover:bg-red-700"
            >
              {pending ? "Annulation…" : "Annuler l’événement"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
