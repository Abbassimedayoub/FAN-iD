import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { AppError } from "@/lib/errors";

import { approveOrganizer, rejectOrganizer, suspendOrganizer } from "./api";
import type { Organizer } from "./types";
import { organizerQueryKeys } from "./useOrganizers";

interface OrganizerMutationVariables {
  organizerId: string;
  version: number;
}

interface RejectOrganizerVariables extends OrganizerMutationVariables {
  reason: string;
}

function useOrganizerMutationCache() {
  const queryClient = useQueryClient();

  return (organizer: Organizer) => {
    queryClient.setQueryData(organizerQueryKeys.detail(organizer.id), organizer);
    void queryClient.invalidateQueries({
      queryKey: organizerQueryKeys.lists(),
    });
  };
}

export function useApproveOrganizer() {
  const updateCache = useOrganizerMutationCache();

  return useMutation<Organizer, AppError, OrganizerMutationVariables>({
    mutationFn: ({ organizerId, version }) => approveOrganizer(organizerId, version),
    onSuccess: updateCache,
  });
}

export function useRejectOrganizer() {
  const updateCache = useOrganizerMutationCache();

  return useMutation<Organizer, AppError, RejectOrganizerVariables>({
    mutationFn: ({ organizerId, version, reason }) => rejectOrganizer(organizerId, version, reason),
    onSuccess: updateCache,
  });
}

export function useSuspendOrganizer() {
  const updateCache = useOrganizerMutationCache();

  return useMutation<Organizer, AppError, OrganizerMutationVariables>({
    mutationFn: ({ organizerId, version }) => suspendOrganizer(organizerId, version),
    onSuccess: updateCache,
  });
}
