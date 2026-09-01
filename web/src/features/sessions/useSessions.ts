import { useQuery } from "@tanstack/react-query";

import type { AppError } from "@/lib/errors";

import { listSessions } from "./api";
import type { AuthSession } from "./types";

export const sessionsQueryKey = ["auth", "sessions"] as const;

export function useSessions() {
  return useQuery<AuthSession[], AppError>({
    queryKey: sessionsQueryKey,
    queryFn: listSessions,
  });
}
