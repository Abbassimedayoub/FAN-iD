import { httpClient } from "@/lib/httpClient";

import type { OrganizerStatus } from "./types";

export const COMMISSION_STATUSES = ["NEGOTIATING", "COMMISSION_AGREED", "CANCELLED"] as const;

export type CommissionStatus = (typeof COMMISSION_STATUSES)[number];

export type CommissionProposerRole = "ORGANIZER" | "ADMIN";

export interface OrganizerCommissionProposal {
  id: string;
  sequence: number;
  proposer_role: CommissionProposerRole;
  proposed_by_id: string;
  rate: string;
  created_at: string;
  accepted_at: string | null;
  accepted_by_id: string | null;
}

export interface OrganizerCommissionNegotiation {
  organizer_id: string;
  validation_status: OrganizerStatus;
  commission_status: CommissionStatus;
  agreed_rate: string | null;
  agreed_at: string | null;
  version: number;
  proposals: OrganizerCommissionProposal[];
}

export const organizerCommissionQueryKeys = {
  my: ["organizer", "commission", "me"] as const,
  admin: (organizerId: string) => ["organizer", "commission", "admin", organizerId] as const,
};

function versionHeaders(version: number) {
  return {
    "If-Match": `"${version}"`,
  };
}

export function commissionPercentToRate(percent: string): string {
  const normalized = percent.trim().replace(",", ".");
  const numeric = Number(normalized);

  if (!Number.isFinite(numeric) || numeric < 0 || numeric > 100) {
    throw new Error("COMMISSION_PERCENT_INVALID");
  }

  return (numeric / 100).toFixed(4);
}

export function formatCommissionRate(rate: string | null): string {
  if (rate === null) {
    return "—";
  }

  const numeric = Number(rate);

  if (!Number.isFinite(numeric)) {
    return rate;
  }

  return `${new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
  }).format(numeric * 100)} %`;
}

export function formatCommissionDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export async function fetchMyCommissionNegotiation(): Promise<OrganizerCommissionNegotiation> {
  const response = await httpClient.get<OrganizerCommissionNegotiation>(
    "/api/v1/organizers/me/commission-negotiation",
  );

  return response.data;
}

export async function createMyCommissionProposal(
  version: number,
  commissionRate: string,
): Promise<OrganizerCommissionNegotiation> {
  const response = await httpClient.post<OrganizerCommissionNegotiation>(
    "/api/v1/organizers/me/commission-proposals",
    {
      commission_rate: commissionRate,
    },
    {
      headers: versionHeaders(version),
    },
  );

  return response.data;
}

export async function acceptMyCommissionProposal(
  version: number,
): Promise<OrganizerCommissionNegotiation> {
  const response = await httpClient.post<OrganizerCommissionNegotiation>(
    "/api/v1/organizers/me/commission-accept",
    undefined,
    {
      headers: versionHeaders(version),
    },
  );

  return response.data;
}

export async function fetchAdminCommissionNegotiation(
  organizerId: string,
): Promise<OrganizerCommissionNegotiation> {
  const response = await httpClient.get<OrganizerCommissionNegotiation>(
    `/api/v1/admin/organizers/${organizerId}/commission-negotiation`,
  );

  return response.data;
}

export async function createAdminCommissionProposal(
  organizerId: string,
  version: number,
  commissionRate: string,
): Promise<OrganizerCommissionNegotiation> {
  const response = await httpClient.post<OrganizerCommissionNegotiation>(
    `/api/v1/admin/organizers/${organizerId}/commission-proposals`,
    {
      commission_rate: commissionRate,
    },
    {
      headers: versionHeaders(version),
    },
  );

  return response.data;
}

export async function acceptAdminCommissionProposal(
  organizerId: string,
  version: number,
): Promise<OrganizerCommissionNegotiation> {
  const response = await httpClient.post<OrganizerCommissionNegotiation>(
    `/api/v1/admin/organizers/${organizerId}/commission-accept`,
    undefined,
    {
      headers: versionHeaders(version),
    },
  );

  return response.data;
}
