import { useEffect, useState } from "react";

import { Button, Modal } from "@/components/primitives";

interface ConfirmationDialogProps {
  open: boolean;
  isPending: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  onClose: () => void;
  onConfirm: () => Promise<boolean>;
}

function ConfirmationDialog({
  open,
  isPending,
  title,
  description,
  confirmLabel,
  onClose,
  onConfirm,
}: ConfirmationDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const busy = isPending || isSubmitting;

  async function confirm() {
    if (busy) return;

    setIsSubmitting(true);

    try {
      const shouldClose = await onConfirm();

      if (shouldClose) {
        onClose();
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!busy) onClose();
      }}
      title={title}
    >
      <p className="text-sm text-navy/70">{description}</p>

      <div className="mt-5 flex flex-wrap justify-end gap-3">
        <Button type="button" disabled={busy} onClick={onClose} className="bg-navy">
          Annuler
        </Button>

        <Button type="button" disabled={busy} onClick={() => void confirm()}>
          {busy ? "Traitement…" : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

export function ApproveDialog({
  open,
  isPending,
  onClose,
  onConfirm,
}: {
  open: boolean;
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => Promise<boolean>;
}) {
  return (
    <ConfirmationDialog
      open={open}
      isPending={isPending}
      title="Approuver la demande"
      description="Confirmez l’approbation de cet organisateur."
      confirmLabel="Confirmer l’approbation"
      onClose={onClose}
      onConfirm={onConfirm}
    />
  );
}

export function RejectDialog({
  open,
  isPending,
  onClose,
  onConfirm,
}: {
  open: boolean;
  isPending: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<boolean>;
}) {
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const busy = isPending || isSubmitting;
  const normalizedReason = reason.trim();

  useEffect(() => {
    if (!open) {
      setReason("");
    }
  }, [open]);

  async function confirm() {
    if (busy || normalizedReason.length === 0) return;

    setIsSubmitting(true);

    try {
      const shouldClose = await onConfirm(normalizedReason);

      if (shouldClose) {
        onClose();
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!busy) onClose();
      }}
      title="Rejeter la demande"
    >
      <label htmlFor="organizer-rejection-reason" className="block text-sm font-medium text-navy">
        Motif du rejet
      </label>

      <textarea
        id="organizer-rejection-reason"
        value={reason}
        maxLength={2000}
        disabled={busy}
        onChange={(event) => setReason(event.target.value)}
        className="mt-2 min-h-32 w-full rounded-md border border-navy/20 px-3 py-2 focus:border-primary disabled:opacity-50"
      />

      <div className="mt-5 flex flex-wrap justify-end gap-3">
        <Button type="button" disabled={busy} onClick={onClose} className="bg-navy">
          Annuler
        </Button>

        <Button
          type="button"
          disabled={busy || normalizedReason.length === 0}
          onClick={() => void confirm()}
          className="bg-red-600"
        >
          {busy ? "Traitement…" : "Confirmer le rejet"}
        </Button>
      </div>
    </Modal>
  );
}

export function SuspendDialog({
  open,
  isPending,
  onClose,
  onConfirm,
}: {
  open: boolean;
  isPending: boolean;
  onClose: () => void;
  onConfirm: () => Promise<boolean>;
}) {
  return (
    <ConfirmationDialog
      open={open}
      isPending={isPending}
      title="Suspendre l’organisateur"
      description="Confirmez la suspension de cet organisateur."
      confirmLabel="Confirmer la suspension"
      onClose={onClose}
      onConfirm={onConfirm}
    />
  );
}
