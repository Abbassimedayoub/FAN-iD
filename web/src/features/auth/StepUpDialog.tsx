import { useEffect, useState } from "react";

import { Button, Input, Modal } from "@/components/primitives";

interface StepUpDialogProps {
  open: boolean;
  expiresInSeconds: number;
  error: string | null;
  onClose: () => void;
  onConfirm: (code: string) => Promise<boolean>;
}

export function StepUpDialog({
  open,
  expiresInSeconds,
  error,
  onClose,
  onConfirm,
}: StepUpDialogProps) {
  const [code, setCode] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const normalizedCode = code.trim();
  const busy = isSubmitting;

  useEffect(() => {
    if (!open) {
      setCode("");
    }
  }, [open]);

  async function confirm() {
    if (busy || normalizedCode.length === 0) return;

    setIsSubmitting(true);

    try {
      const shouldClose = await onConfirm(normalizedCode);

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
      title="Vérification renforcée"
    >
      <p className="text-sm text-navy/70">
        Saisissez le code de vérification envoyé pour confirmer cette action sensible.
      </p>

      <p className="mt-2 text-sm text-navy/60">Le code expire dans {expiresInSeconds} secondes.</p>

      <label htmlFor="step-up-code" className="mt-5 block text-sm font-medium text-navy">
        Code de vérification
      </label>

      <Input
        id="step-up-code"
        value={code}
        maxLength={16}
        autoComplete="one-time-code"
        disabled={busy}
        onChange={(event) => setCode(event.target.value)}
        className="mt-2 w-full"
      />

      {error ? (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {error}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap justify-end gap-3">
        <Button type="button" disabled={busy} onClick={onClose} className="bg-navy">
          Annuler
        </Button>

        <Button
          type="button"
          disabled={busy || normalizedCode.length === 0}
          onClick={() => void confirm()}
        >
          {busy ? "Vérification…" : "Confirmer le code"}
        </Button>
      </div>
    </Modal>
  );
}
