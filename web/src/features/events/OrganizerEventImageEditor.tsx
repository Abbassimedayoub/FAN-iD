import { useRef, useState } from "react";

import { uploadEventImage } from "./api";
import type { OrganizerEvent } from "./types";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

type OrganizerEventImageEditorProps = {
  event: OrganizerEvent;
  onUpdated: (event: OrganizerEvent) => void | Promise<void>;
};

export function OrganizerEventImageEditor({ event, onUpdated }: OrganizerEventImageEditorProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const imageEditable = event.status === "PUBLISHED" || event.status === "POSTPONED";

  if (!imageEditable) {
    return null;
  }

  async function selectImage(file: File | undefined): Promise<void> {
    if (!file) {
      return;
    }

    setError(null);
    setSuccess(null);

    if (!["image/png", "image/jpeg"].includes(file.type)) {
      setError("Utilisez une image PNG ou JPG.");
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setError("L’image ne doit pas dépasser 5 Mo.");
      return;
    }

    setPending(true);

    try {
      const updated = await uploadEventImage(event, file);

      await onUpdated(updated);

      setSuccess(
        event.image_url
          ? "La photo de l’événement a été remplacée."
          : "La photo de l’événement a été ajoutée.",
      );
    } catch {
      setError(
        "Impossible d’enregistrer la photo. " + "L’événement a peut-être été modifié ailleurs.",
      );
    } finally {
      setPending(false);

      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  }

  return (
    <div className="min-w-[220px]">
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="sr-only"
        aria-label="Photo de l’événement"
        disabled={pending}
        onChange={(event) => {
          void selectImage(event.target.files?.[0]);
        }}
      />

      <button
        type="button"
        disabled={pending}
        onClick={() => inputRef.current?.click()}
        className="inline-flex min-h-[44px] w-full items-center justify-center rounded-xl border border-[#1769d2] bg-white px-5 text-sm font-semibold text-[#1769d2] transition hover:bg-[#f3f8ff] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending
          ? "Envoi de la photo…"
          : event.image_url
            ? "Remplacer la photo"
            : "Ajouter une photo"}
      </button>

      <p className="mt-2 max-w-xs text-xs leading-5 text-[#7b8998]">
        PNG ou JPG, 5 Mo maximum. La modification de la photo ne change pas le statut de
        l’événement.
      </p>

      {error ? (
        <p role="alert" className="mt-2 max-w-xs text-xs font-medium text-red-600">
          {error}
        </p>
      ) : null}

      {success ? (
        <p role="status" className="mt-2 max-w-xs text-xs font-medium text-emerald-700">
          {success}
        </p>
      ) : null}
    </div>
  );
}
