export const ORGANIZER_STATUSES = ["PENDING", "APPROVED", "REJECTED", "SUSPENDED"] as const;

export type OrganizerStatus = (typeof ORGANIZER_STATUSES)[number];

export interface Organizer {
  id: string;
  org_name: string;
  validation_status: OrganizerStatus;
  commission_rate: string;
  vat_number: string | null;
  contact_email: string;
  rejection_reason: string | null;
  validated_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface OrganizerPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: Organizer[];
}

export interface OrganizerFilters {
  page: number;
  validationStatus: OrganizerStatus | undefined;
}
