export interface EventCategory {
  id: string;
  name: string;
  description: string;
  version: number;
  is_owned_by_me: boolean;
  can_delete: boolean;
}

export type OrganizerEventStatus =
  "DRAFT" | "PUBLISHED" | "POSTPONED" | "SUSPENDED" | "CANCELLED" | "ARCHIVED";

export interface OrganizerEvent {
  id: string;
  organizer_id: string;
  category_id: string;
  name: string;
  description: string;
  starts_at: string;
  ends_at: string;
  postponed_from_starts_at: string | null;
  postponed_from_ends_at: string | null;
  postponed_to_starts_at: string | null;
  postponed_to_ends_at: string | null;
  venue: string;
  capacity_total: number | null;
  image_url: string | null;
  status: OrganizerEventStatus;
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
