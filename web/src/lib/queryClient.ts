/**
 * Configuration TanStack Query (§4.3 Source B) : staleTime 30s, gcTime 5min,
 * retry 3 avec backoff exponentiel SAUF sur 4xx (rejouer une erreur métier
 * est inutile et masque le vrai problème), refetchOnWindowFocus activé.
 */
import { QueryClient } from "@tanstack/react-query";

import type { AppError } from "./errors";

function isRetryableError(error: unknown): boolean {
  const appError = error as Partial<AppError>;
  if (appError?.httpStatus == null) return true; // erreur réseau : on retente
  return appError.httpStatus >= 500;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: true,
      retry: (failureCount, error) => failureCount < 3 && isRetryableError(error),
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10_000),
    },
    mutations: {
      retry: false, // une mutation ne se rejoue jamais automatiquement (idempotence côté serveur, ADR-S-06)
    },
  },
});
