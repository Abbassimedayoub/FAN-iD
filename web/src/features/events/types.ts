export interface EventCategory {
  id: string;
  name: string;
  description: string;
  version: number;
  is_owned_by_me: boolean;
  can_delete: boolean;
}

export type OrganizerEventStatus =
  "DRAFT" | "PUBLISHED" | "POSTPONED" | "SUSPENDED" | "CANCELLED" | "COMPLETED" | "ARCHIVED";

export type EventOperationalStatus =
  | OrganizerEventStatus
  | "COMING_SOON"
  | "SALE_OPEN"
  | "SALE_CLOSED"
  | "LIVE"
  | "ENDED";

export interface OrganizerEvent {
  id: string;
  organizer_id: string;
  category_id: string;
  name: string;
  description: string;
  starts_at: string;
  ends_at: string;
  sales_starts_at?: string | null;
  sales_ends_at?: string | null;
  postponed_from_starts_at: string | null;
  postponed_from_ends_at: string | null;
  postponed_to_starts_at: string | null;
  postponed_to_ends_at: string | null;
  venue: string;
  capacity_total: number | null;
  image_url: string | null;
  status: OrganizerEventStatus;
  operational_status?: EventOperationalStatus;
  published_at: string | null;
  lifecycle_reason: string;
  lifecycle_changed_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface EventDraftInput {
  category_id: string;
  name: string;
  description: string;
  starts_at: string;
  ends_at: string;
  sales_starts_at: string | null;
  sales_ends_at: string | null;
  venue: string;
  capacity_total: number | null;
}

export interface TicketCategory {
  id: string;
  event_id: string;
  name: string;
  quota: number;
  sold_count: number;
  available_count: number;
  unit_price_cents: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TicketCategoryInput {
  name: string;
  quota: number;
  unit_price_cents: number;
}

export interface EventPostponeInput {
  starts_at: string | null;
  ends_at: string | null;
  reason: string;
  notify_buyers: boolean;
}

export interface EventSuspendInput {
  reason: string;
  notify_buyers: boolean;
}

export interface EventCancelInput {
  reason: string;
  notify_buyers: boolean;
  refund_requested: boolean;
}

export type EventScannerAssignmentStatus =
  | "INVITED"
  | "EMAIL_SENT"
  | "OPENED"
  | "ACTIVE"
  | "LEAVE_REQUESTED"
  | "INVITATION_CANCELLED"
  | "DELETED";

export interface EventScannerAssignment {
  assignment_id: string;
  scanner_id: string;
  first_name: string;
  last_name: string;
  email: string;
  status: EventScannerAssignmentStatus;
  scanner_version: number;
  assigned_at: string;
}


export interface EventAdmissionStatus {
  event_id: string;
  is_open: boolean;
  opened_at: string | null;
  opened_by_id: string | null;
}


export interface EventLiveDashboard {
  event_id: string;
  event_name: string;
  generated_at: string;
  admission: {
    is_open: boolean;
    opened_at: string | null;
  };
  ticketing: {
    sold_count: number;
    remaining_count: number;
    quota_total: number;
  };
  capacity: {
    total: number | null;
    entries_count: number;
    entry_rate_percent: number;
    capacity_rate_percent: number;
  };
  scanners: {
    assigned_count: number;
    present_count: number;
    absent_count: number;
    items: Array<{
      scanner_id: string;
      name: string;
      email: string;
      scan_count: number;
      last_activity: string | null;
      last_seen_at: string | null;
      is_present: boolean;
    }>;
  };
}
