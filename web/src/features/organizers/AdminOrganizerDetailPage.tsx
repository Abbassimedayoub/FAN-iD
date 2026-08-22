import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { confirmStepUp, requestStepUp, type StepUpChallenge } from "@/features/auth/stepUp";
import type { AppError } from "@/lib/errors";

import {
  AdminOrganizerDetailView,
  type OrganizerActionFeedback,
  type OrganizerActionReopen,
} from "./AdminOrganizerDetailView";
import { useOrganizer } from "./useOrganizer";
import {
  useApproveOrganizer,
  useRejectOrganizer,
  useSuspendOrganizer,
} from "./useOrganizerMutations";

type PendingOrganizerAction =
  | {
      kind: "approve";
      version: number;
      successMessage: string;
    }
  | {
      kind: "reject";
      version: number;
      reason: string;
      successMessage: string;
    }
  | {
      kind: "suspend";
      version: number;
      successMessage: string;
    };

interface StepUpState {
  challenge: StepUpChallenge;
  action: PendingOrganizerAction;
}

function toReopenAction(action: PendingOrganizerAction): OrganizerActionReopen {
  if (action.kind === "reject") {
    return {
      kind: action.kind,
      rejectReason: action.reason,
    };
  }

  return {
    kind: action.kind,
  };
}

export function AdminOrganizerDetailPage() {
  const navigate = useNavigate();
  const { organizerId = "" } = useParams<{ organizerId: string }>();

  const query = useOrganizer(organizerId);
  const approve = useApproveOrganizer();
  const reject = useRejectOrganizer();
  const suspend = useSuspendOrganizer();

  const [feedback, setFeedback] = useState<OrganizerActionFeedback | null>(null);
  const [isStaleResource, setIsStaleResource] = useState(false);
  const [stepUpState, setStepUpState] = useState<StepUpState | null>(null);
  const [stepUpError, setStepUpError] = useState<string | null>(null);
  const [reopenAction, setReopenAction] = useState<OrganizerActionReopen | null>(null);

  const isActionPending = approve.isPending || reject.isPending || suspend.isPending;

  async function executeOrganizerAction(action: PendingOrganizerAction): Promise<void> {
    if (action.kind === "approve") {
      await approve.mutateAsync({
        organizerId,
        version: action.version,
      });
      return;
    }

    if (action.kind === "reject") {
      await reject.mutateAsync({
        organizerId,
        version: action.version,
        reason: action.reason,
      });
      return;
    }

    await suspend.mutateAsync({
      organizerId,
      version: action.version,
    });
  }

  function showActionSuccess(action: PendingOrganizerAction) {
    setFeedback({
      message: action.successMessage,
      tone: "success",
    });
  }

  function showActionFailure(appError: AppError) {
    if (appError.code === "STALE_RESOURCE") {
      setIsStaleResource(true);
      return;
    }

    setFeedback({
      message: appError.message || "L’action a échoué. Réessayez.",
      tone: "danger",
    });
  }

  async function runAction(action: PendingOrganizerAction): Promise<boolean> {
    setFeedback(null);
    setReopenAction(null);

    try {
      await executeOrganizerAction(action);
      showActionSuccess(action);
      return true;
    } catch (error) {
      const appError = error as AppError;

      if (appError.code === "STALE_RESOURCE") {
        showActionFailure(appError);
        return true;
      }

      if (appError.code === "STEP_UP_REQUIRED") {
        try {
          const challenge = await requestStepUp();

          setStepUpError(null);
          setStepUpState({
            action,
            challenge,
          });

          return true;
        } catch (requestError) {
          showActionFailure(requestError as AppError);
          return false;
        }
      }

      showActionFailure(appError);
      return false;
    }
  }

  async function confirmPendingStepUp(pending: StepUpState, code: string): Promise<boolean> {
    setStepUpError(null);

    try {
      await confirmStepUp(pending.challenge.challenge_id, code);
    } catch (error) {
      const appError = error as AppError;

      setStepUpError(appError.message || "La vérification a échoué. Réessayez.");
      return false;
    }

    try {
      await executeOrganizerAction(pending.action);
      showActionSuccess(pending.action);
      setStepUpState(null);
      return true;
    } catch (error) {
      const appError = error as AppError;

      showActionFailure(appError);
      setStepUpState(null);

      if (appError.code !== "STALE_RESOURCE") {
        setReopenAction(toReopenAction(pending.action));
      }

      return true;
    }
  }

  function closeStepUp() {
    setStepUpState(null);
    setStepUpError(null);
  }

  function reloadStaleResource() {
    setIsStaleResource(false);
    setFeedback(null);
    setStepUpState(null);
    setStepUpError(null);
    setReopenAction(null);

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
        reopenAction,
        onClearReopenAction: () => setReopenAction(null),
        onApprove: () => {
          if (currentVersion == null) return Promise.resolve(false);

          return runAction({
            kind: "approve",
            version: currentVersion,
            successMessage: "Demande approuvée.",
          });
        },
        onReject: (reason) => {
          if (currentVersion == null) return Promise.resolve(false);

          return runAction({
            kind: "reject",
            version: currentVersion,
            reason,
            successMessage: "Demande rejetée.",
          });
        },
        onSuspend: () => {
          if (currentVersion == null) return Promise.resolve(false);

          return runAction({
            kind: "suspend",
            version: currentVersion,
            successMessage: "Organisateur suspendu.",
          });
        },
        onReloadStale: reloadStaleResource,
        stepUp: stepUpState
          ? {
              expiresInSeconds: stepUpState.challenge.expires_in_seconds,
              error: stepUpError,
              onClose: closeStepUp,
              onConfirm: (code) => confirmPendingStepUp(stepUpState, code),
            }
          : undefined,
      }}
    />
  );
}
