import { Badge, type BadgeTone } from "@/components/primitives";

import type { OrganizerStatus } from "./types";

const STATUS_LABELS: Record<OrganizerStatus, string> = {
  PENDING: "En attente",
  APPROVED: "Approuvé",
  REJECTED: "Rejeté",
  SUSPENDED: "Suspendu",
};

const STATUS_TONES: Record<OrganizerStatus, BadgeTone> = {
  PENDING: "warning",
  APPROVED: "success",
  REJECTED: "danger",
  SUSPENDED: "warning",
};

export function OrganizerStatusBadge({ status }: { status: OrganizerStatus }) {
  return <Badge tone={STATUS_TONES[status]}>{STATUS_LABELS[status]}</Badge>;
}
