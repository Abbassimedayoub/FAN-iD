import { httpClient } from "@/lib/httpClient";

import type { Organizer, OrganizerFilters, OrganizerPage } from "./types";

function organizerActionHeaders(version: number) {
  return {
    "If-Match": `"${version}"`,
  };
}

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

export async function approveOrganizer(organizerId: string, version: number): Promise<Organizer> {
  const response = await httpClient.post<Organizer>(
    `/api/v1/admin/organizers/${organizerId}/approve`,
    undefined,
    {
      headers: organizerActionHeaders(version),
    },
  );

  return response.data;
}

export async function rejectOrganizer(
  organizerId: string,
  version: number,
  reason: string,
): Promise<Organizer> {
  const response = await httpClient.post<Organizer>(
    `/api/v1/admin/organizers/${organizerId}/reject`,
    { reason },
    {
      headers: organizerActionHeaders(version),
    },
  );

  return response.data;
}

export async function suspendOrganizer(organizerId: string, version: number): Promise<Organizer> {
  const response = await httpClient.post<Organizer>(
    `/api/v1/admin/organizers/${organizerId}/suspend`,
    undefined,
    {
      headers: organizerActionHeaders(version),
    },
  );

  return response.data;
}
