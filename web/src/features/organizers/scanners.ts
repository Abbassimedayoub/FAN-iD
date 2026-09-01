import { httpClient } from "@/lib/httpClient";

export const SCANNER_STATUSES = [
  "INVITED",
  "EMAIL_SENT",
  "OPENED",
  "ACTIVE",
  "LEAVE_REQUESTED",
  "INVITATION_CANCELLED",
  "DELETED",
] as const;

export type ScannerStatus = (typeof SCANNER_STATUSES)[number];

export interface OrganizerScanner {
  id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  status: ScannerStatus;
  scanner_email_sent_at: string | null;
  organizer_email_sent_at: string | null;
  opened_at: string | null;
  activated_at: string | null;
  removed_at: string | null;
  archived_at: string | null;
  password_help_pending?: boolean;
  password_help_requested_at?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface OrganizerScannerPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: OrganizerScanner[];
}

export interface OrganizerScannerListParams {
  page?: number;
  search?: string;
  status?: ScannerStatus;
}

export interface InviteScannerInput {
  first_name: string;
  last_name: string;
  email: string;
}

export const organizerScannersQueryKey = ["organizing", "organizer-scanners"] as const;

function normalizeScannerPage(
  data: OrganizerScannerPage | OrganizerScanner[],
): OrganizerScannerPage {
  if (Array.isArray(data)) {
    return {
      count: data.length,
      next: null,
      previous: null,
      results: data,
    };
  }

  return data;
}

export async function fetchOrganizerScannersPage(
  params: OrganizerScannerListParams = {},
): Promise<OrganizerScannerPage> {
  const queryParams: Record<string, string | number> = {
    page: params.page ?? 1,
  };

  const search = params.search?.trim();

  if (search) {
    queryParams.search = search;
  }

  if (params.status) {
    queryParams.status = params.status;
  }

  const response = await httpClient.get<
    OrganizerScannerPage | OrganizerScanner[]
  >("/api/v1/organizers/me/scanners", {
    params: queryParams,
  });

  return normalizeScannerPage(response.data);
}

export async function fetchOrganizerScanners(): Promise<OrganizerScanner[]> {
  const firstPage = await fetchOrganizerScannersPage({
    page: 1,
  });

  const scanners = [...firstPage.results];

  if (scanners.length >= firstPage.count) {
    return scanners;
  }

  const totalPages = Math.ceil(firstPage.count / 5);

  for (let page = 2; page <= totalPages; page += 1) {
    const nextPage = await fetchOrganizerScannersPage({
      page,
    });

    scanners.push(...nextPage.results);
  }

  return scanners;
}

export async function inviteOrganizerScanner(input: InviteScannerInput): Promise<OrganizerScanner> {
  const response = await httpClient.post<OrganizerScanner>("/api/v1/organizers/me/scanners", {
    first_name: input.first_name.trim(),
    last_name: input.last_name.trim(),
    email: input.email.trim(),
  });

  return response.data;
}

export type ScannerLeaveDecision = "ACCEPT" | "REJECT";

export type ScannerSecurityAction = "REVOKE" | "LEAVE_ACCEPT";

export interface ScannerSecurityChallenge {
  challenge_id: string;
  expires_in_seconds: number;
}

export interface ScannerSecurityOtp {
  challenge_id: string;
  code: string;
}

export async function requestOrganizerScannerSecurityCode(
  scanner: OrganizerScanner,
  action: ScannerSecurityAction,
): Promise<ScannerSecurityChallenge> {
  const response = await httpClient.post<ScannerSecurityChallenge>(
    `/api/v1/organizers/me/scanners/${scanner.id}/security-code`,
    {
      action,
    },
  );

  return response.data;
}

export async function decideOrganizerScannerLeave(
  scanner: OrganizerScanner,
  decision: ScannerLeaveDecision,
  otp?: ScannerSecurityOtp,
): Promise<void> {
  await httpClient.post(
    `/api/v1/organizers/me/scanners/${scanner.id}/leave-request`,
    {
      decision,
      ...(decision === "ACCEPT" && otp ? otp : {}),
    },
    {
      headers: {
        "If-Match": `"${scanner.version}"`,
      },
    },
  );
}

export async function revokeOrganizerScanner(
  scanner: OrganizerScanner,
  otp: ScannerSecurityOtp,
): Promise<void> {
  await httpClient.delete(`/api/v1/organizers/me/scanners/${scanner.id}`, {
    data: otp,
    headers: {
      "If-Match": `"${scanner.version}"`,
    },
  });
}

export async function reissueOrganizerScannerPassword(scanner: OrganizerScanner): Promise<void> {
  await httpClient.post(`/api/v1/organizers/me/scanners/${scanner.id}/temporary-password`, {});
}

export async function resendOrganizerScannerInvitation(
  scanner: OrganizerScanner,
): Promise<OrganizerScanner> {
  const response = await httpClient.post<OrganizerScanner>(
    `/api/v1/organizers/me/scanners/${scanner.id}/resend-invitation`,
    {},
  );

  return response.data;
}

export async function archiveOrganizerScanners(
  scanners: OrganizerScanner[],
): Promise<{ archived: number }> {
  const response = await httpClient.post<{ archived: number }>(
    "/api/v1/organizers/me/scanners/archive",
    {
      scanners: scanners.map((scanner) => ({
        id: scanner.id,
        version: scanner.version,
      })),
    },
  );

  return response.data;
}

export const organizerArchivedScannersQueryKey = [
  "organizing",
  "organizer-scanners",
  "archived",
] as const;

export interface OrganizerArchivedScannerListParams {
  page?: number;
  search?: string;
  status?: Extract<
    ScannerStatus,
    "INVITATION_CANCELLED" | "DELETED"
  >;
}

export async function fetchOrganizerArchivedScannersPage(
  params: OrganizerArchivedScannerListParams = {},
): Promise<OrganizerScannerPage> {
  const queryParams: Record<string, string | number> = {
    page: params.page ?? 1,
  };

  const search = params.search?.trim();

  if (search) {
    queryParams.search = search;
  }

  if (params.status) {
    queryParams.status = params.status;
  }

  const response = await httpClient.get<
    OrganizerScannerPage | OrganizerScanner[]
  >(
    "/api/v1/organizers/me/scanners/archived",
    {
      params: queryParams,
    },
  );

  return normalizeScannerPage(response.data);
}

export async function fetchOrganizerArchivedScanners(): Promise<
  OrganizerScanner[]
> {
  const firstPage = await fetchOrganizerArchivedScannersPage({
    page: 1,
  });

  const scanners = [...firstPage.results];

  if (scanners.length >= firstPage.count) {
    return scanners;
  }

  const totalPages = Math.ceil(firstPage.count / 5);

  for (
    let page = 2;
    page <= totalPages;
    page += 1
  ) {
    const nextPage =
      await fetchOrganizerArchivedScannersPage({
        page,
      });

    scanners.push(...nextPage.results);
  }

  return scanners;
}
