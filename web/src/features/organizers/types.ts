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

export interface AdminOrganizerPendingReactivation {
  id: string;
  organizer_id: string;
  organizer_name: string;
  created_at: string;
}

export interface OrganizerPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: Organizer[];
  pending_reactivation_count?: number;
  pending_reactivations?: AdminOrganizerPendingReactivation[];
}

export interface OrganizerFilters {
  page: number;
  validationStatus: OrganizerStatus | undefined;
}

export interface AdminFinancialOrganizer {
  organizer_id: string;
  org_name: string;
  net_revenue_cents: number;
  completed_events_count: number;
}

export interface AdminFinancialDashboard {
  confirmed_commission_cents: number;
  organizer_count: number;
  organizers: AdminFinancialOrganizer[];
}
