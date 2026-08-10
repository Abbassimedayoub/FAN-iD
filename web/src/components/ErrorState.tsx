/**
 * État `error` (§4.2 Source B) : message selon la CLASSE d'erreur + bouton
 * Réessayer + correlation_id en petit. Jamais de trace technique brute.
 */
import type { AppError } from "@/lib/errors";

import { RetryButton } from "./RetryButton";

const MESSAGES_BY_CLASS: Record<AppError["errorClass"], string> = {
  network: "Connexion indisponible. Vérifiez votre réseau.",
  auth: "Votre session a expiré, merci de vous reconnecter.",
  permission: "Vous n'avez pas accès à cette ressource.",
  not_found: "Cet élément n'existe plus.",
  business: "", // le message métier vient directement de error.message (catalogue par code)
  server: "Un problème est survenu de notre côté.",
  unknown: "Une erreur inattendue est survenue.",
};

interface ErrorStateProps {
  error: AppError;
  onRetry?: () => void;
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const displayMessage = MESSAGES_BY_CLASS[error.errorClass] || error.message;

  return (
    <div role="alert" className="flex flex-col items-center gap-3 py-12 text-center">
      <p className="font-sora text-lg font-semibold text-navy">{displayMessage}</p>
      {onRetry ? <RetryButton onClick={onRetry} /> : null}
      {error.correlationId ? (
        <p className="text-xs text-navy/40">Référence : {error.correlationId}</p>
      ) : null}
    </div>
  );
}
