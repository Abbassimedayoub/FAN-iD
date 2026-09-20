/**
 * TanStack Query configuration: 30 s stale time, 5 min garbage collection,
 * up to three retries with exponential backoff for retryable errors, and
 * refetch on window focus.
 */
import { QueryClient } from "@tanstack/react-query";

import type { AppError } from "./errors";

function isRetryableError(error: unknown): boolean {
  const appError = error as Partial<AppError>;
  if (appError?.httpStatus == null) return true; // Retry network failures.
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
      retry: false, // Mutations are never retried automatically.
    },
  },
});
