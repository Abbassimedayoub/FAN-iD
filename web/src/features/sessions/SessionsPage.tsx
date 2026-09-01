import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AdminShell } from "@/components/AdminShell";
import { useAuth } from "@/features/auth/AuthContext";
import { logoutWeb } from "@/features/auth/logout";

import { SessionsView } from "./SessionsView";
import type { AuthSession } from "./types";
import { useRevokeSession } from "./useRevokeSession";
import { sessionsQueryKey, useSessions } from "./useSessions";

export function SessionsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { clearAuthentication, user } = useAuth();
  const query = useSessions();
  const clearCacheOnUnmount = useRef(false);
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState(false);

  useEffect(() => {
    return () => {
      if (clearCacheOnUnmount.current) {
        queryClient.clear();
        return;
      }

      queryClient.removeQueries({
        queryKey: sessionsQueryKey,
        exact: true,
      });
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

  function handleBack(): void {
    if (user?.role === "ADMIN") {
      navigate("/admin/organizers");
      return;
    }

    if (user?.role === "ORGANIZER") {
      navigate("/organizer");
      return;
    }

    navigate("/");
  }

  async function handleLogout(): Promise<void> {
    setLogoutPending(true);
    setLogoutError(false);

    try {
      await logoutWeb();

      clearCacheOnUnmount.current = true;
      clearAuthentication();
      navigate("/login", { replace: true });
    } catch {
      setLogoutError(true);
      setLogoutPending(false);
    }
  }

  const commonProps = {
    sessions: query.data,
    isPending: query.isPending,
    isFetching: query.isFetching,
    error: query.isError ? query.error : null,
    revokingSessionId: revokeMutation.variables?.sessionId,
    mutationPending: revokeMutation.isPending,
    mutationError: revokeMutation.isError ? revokeMutation.error : null,
    onRetry: () => {
      void query.refetch();
    },
    onRevoke: handleRevoke,
  };

  if (user?.role === "ADMIN") {
    return (
      <AdminShell>
        <SessionsView {...commonProps} />
      </AdminShell>
    );
  }

  return (
    <SessionsView
      {...commonProps}
      logoutPending={logoutPending}
      logoutError={logoutError}
      onBack={handleBack}
      onLogout={() => {
        void handleLogout();
      }}
    />
  );
}
