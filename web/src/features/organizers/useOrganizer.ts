import { useQuery } from "@tanstack/react-query";

import type { AppError } from "@/lib/errors";

import { fetchOrganizer } from "./api";
import type { Organizer } from "./types";
import { organizerQueryKeys } from "./useOrganizers";

export function useOrganizer(organizerId: string) {
  return useQuery<Organizer, AppError>({
    queryKey: organizerQueryKeys.detail(organizerId),
    queryFn: () => fetchOrganizer(organizerId),
    enabled: organizerId.length > 0,
  });
}
