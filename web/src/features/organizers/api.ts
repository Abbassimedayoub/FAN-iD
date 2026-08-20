import { httpClient } from "@/lib/httpClient";

import type { OrganizerFilters, OrganizerPage } from "./types";

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
