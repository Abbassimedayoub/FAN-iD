import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import type { AppError } from "@/lib/errors";

import { AdminOrganizerDetailView, type OrganizerActionFeedback } from "./AdminOrganizerDetailView";
import { useOrganizer } from "./useOrganizer";
import {
  useApproveOrganizer,
  useRejectOrganizer,
  useSuspendOrganizer,
} from "./useOrganizerMutations";

export function AdminOrganizerDetailPage() {
  const navigate = useNavigate();
  const { organizerId = "" } = useParams<{ organizerId: string }>();

  const query = useOrganizer(organizerId);
  const approve = useApproveOrganizer();
  const reject = useRejectOrganizer();
  const suspend = useSuspendOrganizer();

  const [feedback, setFeedback] = useState<OrganizerActionFeedback | null>(null);
  const [isStaleResource, setIsStaleResource] = useState(false);

  const isActionPending = approve.isPending || reject.isPending || suspend.isPending;

  async function runAction(
    action: () => Promise<unknown>,
    successMessage: string,
  ): Promise<boolean> {
    setFeedback(null);

    try {
      await action();

      setFeedback({
        message: successMessage,
        tone: "success",
      });

      return true;
    } catch (error) {
      const appError = error as AppError;

      if (appError.code === "STALE_RESOURCE") {
        setIsStaleResource(true);
        return true;
      }

      setFeedback({
        message: appError.message || "L’action a échoué. Réessayez.",
        tone: "danger",
      });

      return false;
    }
  }

  function reloadStaleResource() {
    setIsStaleResource(false);
    setFeedback(null);

    approve.reset();
    reject.reset();
    suspend.reset();

    void query.refetch();
  }

  const currentVersion = query.data?.version;

  return (
    <AdminOrganizerDetailView
      data={query.data}
      isPending={query.isPending}
      isFetching={query.isFetching}
      error={query.isError ? query.error : null}
      onRetry={() => {
        void query.refetch();
      }}
      onBack={() => {
        navigate("/admin/organizers");
      }}
      actions={{
        isPending: isActionPending,
        feedback,
        isStaleResource,
        onApprove: () => {
          if (currentVersion == null) return Promise.resolve(false);

          return runAction(
            () =>
              approve.mutateAsync({
                organizerId,
                version: currentVersion,
              }),
            "Demande approuvée.",
          );
        },
        onReject: (reason) => {
          if (currentVersion == null) return Promise.resolve(false);

          return runAction(
            () =>
              reject.mutateAsync({
                organizerId,
                version: currentVersion,
                reason,
              }),
            "Demande rejetée.",
          );
        },
        onSuspend: () => {
          if (currentVersion == null) return Promise.resolve(false);

          return runAction(
            () =>
              suspend.mutateAsync({
                organizerId,
                version: currentVersion,
              }),
            "Organisateur suspendu.",
          );
        },
        onReloadStale: reloadStaleResource,
      }}
    />
  );
}
