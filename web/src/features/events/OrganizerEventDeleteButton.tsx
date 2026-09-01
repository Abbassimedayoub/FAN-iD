import { useState } from "react";

import { Button, Modal } from "@/components/primitives";
import { toAppError } from "@/lib/errors";

import { deleteEventDraft } from "./api";
import type { OrganizerEvent } from "./types";

export function OrganizerEventDeleteButton({
  event,
  onDeleted,
}: {
  event: OrganizerEvent;
  onDeleted: () => Promise<void> | void;
}) {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (event.status !== "DRAFT") {
    return null;
  }

  async function handleDelete(): Promise<void> {
    setPending(true);
    setError(null);

    try {
      await deleteEventDraft(event);
      await onDeleted();
      setOpen(false);
    } catch (caught) {
      setError(toAppError(caught).message);
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <Button
        type="button"
        onClick={() => {
          setError(null);
          setOpen(true);
        }}
        className="flex-1 border border-red-200 bg-white px-4 font-semibold text-red-600 hover:bg-red-50"
      >
        Supprimer définitivement
      </Button>

      <Modal
        open={open}
        onClose={() => {
          if (!pending) {
            setOpen(false);
          }
        }}
        title="Supprimer définitivement"
      >
        <p className="text-sm leading-6 text-[#66788b]">
          Voulez-vous vraiment supprimer définitivement l’événement <strong>{event.name}</strong> ?
        </p>

        <p className="mt-3 text-sm font-medium text-red-600">Cette action est irréversible.</p>

        {error ? (
          <p role="alert" className="mt-4 text-sm font-medium text-red-600">
            {error}
          </p>
        ) : null}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            type="button"
            disabled={pending}
            onClick={() => setOpen(false)}
            className="border border-[#d6dfe8] bg-white text-[#536579] hover:bg-[#f7f9fb]"
          >
            Annuler
          </Button>

          <Button
            type="button"
            disabled={pending}
            onClick={() => {
              void handleDelete();
            }}
            className="bg-red-600 text-white hover:bg-red-700"
          >
            {pending ? "Suppression…" : "Supprimer définitivement"}
          </Button>
        </div>
      </Modal>
    </>
  );
}
