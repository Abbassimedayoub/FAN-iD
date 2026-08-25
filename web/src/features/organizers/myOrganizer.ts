import { httpClient } from "@/lib/httpClient";

import type { Organizer } from "./types";

export const myOrganizerQueryKey = ["organizer", "me"] as const;

export async function fetchMyOrganizer(): Promise<Organizer> {
  const response = await httpClient.get<Organizer>("/api/v1/organizers/me");
  return response.data;
}
