import { keepPreviousData, useQuery } from "@tanstack/react-query";

import type { AppError } from "@/lib/errors";

import { fetchOrganizers } from "./api";
import type { OrganizerFilters, OrganizerPage } from "./types";

export const organizerQueryKeys = {
  all: ["admin-organizers"] as const,
  list: (filters: OrganizerFilters) =>
    [...organizerQueryKeys.all, filters.page, filters.validationStatus ?? "ALL"] as const,
  detail: (organizerId: string) => [...organizerQueryKeys.all, "detail", organizerId] as const,
};

export function useOrganizers(filters: OrganizerFilters) {
  return useQuery<OrganizerPage, AppError>({
    queryKey: organizerQueryKeys.list(filters),
    queryFn: () => fetchOrganizers(filters),
    placeholderData: keepPreviousData,
  });
}
