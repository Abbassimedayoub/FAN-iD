import { EmptyState } from "@/components/EmptyState";
import { ErrorState, getErrorDisplayMessage } from "@/components/ErrorState";
import { RetryButton } from "@/components/RetryButton";
import { Skeleton } from "@/components/Skeleton";
import { Table } from "@/components/primitives";
import type { AppError } from "@/lib/errors";

import { SessionRow } from "./SessionRow";
import type { AuthSession } from "./types";

interface SessionsViewProps {
  sessions: readonly AuthSession[] | undefined;
  isPending: boolean;
  isFetching: boolean;
  error: AppError | null;
  revokingSessionId?: string;
  mutationPending?: boolean;
  mutationError?: AppError | null;
  logoutPending?: boolean;
  logoutError?: boolean;
  onBack?: () => void;
  onLogout?: () => void;
  onRetry: () => void;
  onRevoke: (session: AuthSession) => void;
}

function SessionsTableSkeleton() {
  return (
    <Table aria-label="Chargement des sessions">
      <thead>
        <tr className="border-b border-navy/10">
          <th scope="col" className="px-3 py-3">
            Appareil
          </th>
          <th scope="col" className="px-3 py-3">
            IP
          </th>
          <th scope="col" className="px-3 py-3">
            Navigateur
          </th>
          <th scope="col" className="px-3 py-3">
            Dernière activité
          </th>
          <th scope="col" className="px-3 py-3">
            Action
          </th>
        </tr>
      </thead>

      <tbody>
        {Array.from({ length: 5 }, (_, index) => (
          <tr
            key={index}
            aria-label={`Chargement de la session ${index + 1}`}
            className="border-b border-navy/10"
          >
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-36" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-24" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-44" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-4 w-32" />
            </td>
            <td className="px-3 py-4">
              <Skeleton className="h-11 w-28" />
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function SessionsErrorBanner({ error, onRetry }: { error: AppError; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-red-200 bg-red-50 p-4"
    >
      <div>
        <p className="font-medium text-navy">{getErrorDisplayMessage(error)}</p>
        <p className="mt-1 text-sm text-navy/60">
          Les dernières sessions disponibles restent affichées.
        </p>
        {error.correlationId ? (
          <p className="mt-1 text-xs text-navy/40">Référence : {error.correlationId}</p>
        ) : null}
      </div>

      <RetryButton onClick={onRetry} />
    </div>
  );
}

export function SessionsView({
  sessions,
  isPending,
  isFetching,
  error,
  revokingSessionId,
  mutationPending = false,
  mutationError = null,
  logoutPending = false,
  logoutError = false,
  onBack,
  onLogout,
  onRetry,
  onRevoke,
}: SessionsViewProps) {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-6 md:p-8">
      <header className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-sora text-2xl font-bold text-navy">Mes sessions</h1>

          <p className="mt-2 max-w-2xl text-sm text-navy/70">
            Consultez les sessions actives de votre compte et révoquez celles que vous ne
            reconnaissez plus.
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-[#d7e0e9] bg-white px-4 py-2 text-sm font-semibold text-navy transition hover:bg-navy/5 focus:outline-none focus:ring-4 focus:ring-cyan/10"
            >
              ← Retour
            </button>
          ) : null}

          {onLogout ? (
            <button
              type="button"
              onClick={onLogout}
              disabled={logoutPending}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100 focus:outline-none focus:ring-4 focus:ring-red-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {logoutPending ? "Déconnexion…" : "Se déconnecter"}
            </button>
          ) : null}
        </div>
      </header>

      {logoutError ? (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          Impossible de fermer la session. Réessayez.
        </div>
      ) : null}

      {isFetching && !isPending ? (
        <p role="status" className="text-sm text-navy/60">
          Actualisation des sessions…
        </p>
      ) : null}

      {mutationError ? (
        <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-4">
          <p className="font-medium text-navy">{getErrorDisplayMessage(mutationError)}</p>
          {mutationError.correlationId ? (
            <p className="mt-1 text-xs text-navy/40">Référence : {mutationError.correlationId}</p>
          ) : null}
        </div>
      ) : null}

      {isPending ? <SessionsTableSkeleton /> : null}

      {error && !sessions ? <ErrorState error={error} onRetry={onRetry} /> : null}

      {error && sessions ? <SessionsErrorBanner error={error} onRetry={onRetry} /> : null}

      {sessions ? (
        sessions.length === 0 ? (
          <EmptyState
            title="Aucune session active"
            description="Aucune session active n’est actuellement associée à votre compte."
          />
        ) : (
          <Table aria-label="Sessions actives">
            <caption className="sr-only">Sessions actives du compte</caption>

            <thead>
              <tr className="border-b border-navy/10 text-navy/60">
                <th scope="col" className="px-3 py-3 font-medium">
                  Appareil
                </th>
                <th scope="col" className="px-3 py-3 font-medium">
                  IP
                </th>
                <th scope="col" className="px-3 py-3 font-medium">
                  Navigateur
                </th>
                <th scope="col" className="px-3 py-3 font-medium">
                  Dernière activité
                </th>
                <th scope="col" className="px-3 py-3 font-medium">
                  Action
                </th>
              </tr>
            </thead>

            <tbody>
              {sessions.map((session) => (
                <SessionRow
                  key={session.id}
                  session={session}
                  disabled={mutationPending}
                  isRevoking={mutationPending && revokingSessionId === session.id}
                  onRevoke={onRevoke}
                />
              ))}
            </tbody>
          </Table>
        )
      ) : null}
    </main>
  );
}
