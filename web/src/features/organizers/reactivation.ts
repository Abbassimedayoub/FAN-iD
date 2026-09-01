import { httpClient } from "@/lib/httpClient";

import type { Organizer, OrganizerStatus } from "./types";

export const ORGANIZER_REACTIVATION_STATUSES = [
  "PENDING",
  "APPROVED",
  "REJECTED",
] as const;

export type OrganizerReactivationStatus =
  (typeof ORGANIZER_REACTIVATION_STATUSES)[number];

export interface OrganizerReactivationRequest {
  id: string;
  organizer_id: string;
  requested_by_id: string;
  organizer_version: number;
  status: OrganizerReactivationStatus;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizerReactivationEnvelope {
  request: OrganizerReactivationRequest | null;
}

export interface OrganizerReactivationDecisionResult {
  request: OrganizerReactivationRequest;
  organizer: {
    id: string;
    validation_status: OrganizerStatus;
    version: number;
  };
}

export const organizerReactivationQueryKeys = {
  my: ["organizer", "me", "reactivation-request"] as const,
  admin: (organizerId: string) =>
    ["admin", "organizer", organizerId, "reactivation-request"] as const,
};

function organizerVersionHeaders(version: number) {
  return {
    "If-Match": `"${version}"`,
  };
}

export async function fetchMyOrganizerReactivationRequest(): Promise<OrganizerReactivationEnvelope> {
  const response = await httpClient.get<OrganizerReactivationEnvelope>(
    "/api/v1/organizers/me/reactivation-request",
  );

  return response.data;
}

export async function requestMyOrganizerReactivation(): Promise<OrganizerReactivationRequest> {
  const response = await httpClient.post<OrganizerReactivationRequest>(
    "/api/v1/organizers/me/reactivation-request",
    {},
  );

  return response.data;
}

export async function fetchAdminOrganizerReactivationRequest(
  organizerId: string,
): Promise<OrganizerReactivationEnvelope> {
  const response = await httpClient.get<OrganizerReactivationEnvelope>(
    `/api/v1/admin/organizers/${organizerId}/reactivation-request`,
  );

  return response.data;
}

export async function approveAdminOrganizerReactivation(
  organizerId: string,
  version: number,
): Promise<OrganizerReactivationDecisionResult> {
  const response = await httpClient.post<OrganizerReactivationDecisionResult>(
    `/api/v1/admin/organizers/${organizerId}/reactivation-request/approve`,
    {},
    {
      headers: organizerVersionHeaders(version),
    },
  );

  return response.data;
}

export async function rejectAdminOrganizerReactivation(
  organizerId: string,
  version: number,
  reason: string,
): Promise<OrganizerReactivationDecisionResult> {
  const response = await httpClient.post<OrganizerReactivationDecisionResult>(
    `/api/v1/admin/organizers/${organizerId}/reactivation-request/reject`,
    {
      reason,
    },
    {
      headers: organizerVersionHeaders(version),
    },
  );

  return response.data;
}

export function isSuspendedOrganizer(organizer: Organizer): boolean {
  return organizer.validation_status === "SUSPENDED";
}
