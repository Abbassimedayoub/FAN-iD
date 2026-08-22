import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";

import { SessionsView } from "./SessionsView";
import type { AuthSession } from "./types";
import { useRevokeSession } from "./useRevokeSession";
import { useSessions } from "./useSessions";

export function SessionsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { clearAuthentication } = useAuth();
  const query = useSessions();
  const clearCacheOnUnmount = useRef(false);

  useEffect(() => {
    return () => {
      if (clearCacheOnUnmount.current) {
        queryClient.clear();
      }
    };
  }, [queryClient]);

  const revokeMutation = useRevokeSession({
    onCurrentSessionRevoked: () => {
      clearCacheOnUnmount.current = true;
      clearAuthentication();
      navigate("/login", { replace: true });
    },
  });

  function handleRevoke(session: AuthSession): void {
    revokeMutation.mutate({
      sessionId: session.id,
      current: session.current,
    });
  }

  return (
    <SessionsView
      sessions={query.data}
      isPending={query.isPending}
      isFetching={query.isFetching}
      error={query.isError ? query.error : null}
      revokingSessionId={revokeMutation.variables?.sessionId}
      mutationPending={revokeMutation.isPending}
      mutationError={revokeMutation.isError ? revokeMutation.error : null}
      onRetry={() => {
        void query.refetch();
      }}
      onRevoke={handleRevoke}
    />
  );
}
