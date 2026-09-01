import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { AppError } from "@/lib/errors";

import { revokeSession } from "./api";
import { sessionsQueryKey } from "./useSessions";

export interface RevokeSessionVariables {
  sessionId: string;
  current: boolean;
}

interface UseRevokeSessionOptions {
  onCurrentSessionRevoked?: () => void;
}

export function useRevokeSession(options: UseRevokeSessionOptions = {}) {
  const queryClient = useQueryClient();

  return useMutation<void, AppError, RevokeSessionVariables>({
    mutationFn: ({ sessionId }) => revokeSession(sessionId),
    onSuccess: (_data, variables) => {
      if (variables.current) {
        options.onCurrentSessionRevoked?.();
        return;
      }

      void queryClient.invalidateQueries({
        queryKey: sessionsQueryKey,
      });
    },
  });
}
