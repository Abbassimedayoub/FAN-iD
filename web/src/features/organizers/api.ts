import { httpClient } from "@/lib/httpClient";

import type { Organizer, OrganizerFilters, OrganizerPage } from "./types";

export async function fetchOrganizers(filters: OrganizerFilters): Promise<OrganizerPage> {
  const params: Record<string, string | number> = {
    page: filters.page,
  };

  if (filters.validationStatus) {
    params["validation_status"] = filters.validationStatus;
  }

  const response = await httpClient.get<OrganizerPage>("/api/v1/admin/organizers/", {
    params,
  });

  return response.data;
}

export async function fetchOrganizer(organizerId: string): Promise<Organizer> {
  const response = await httpClient.get<Organizer>(`/api/v1/admin/organizers/${organizerId}`);

  return response.data;
}
