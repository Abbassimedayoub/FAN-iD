import { describe, expect, it } from "vitest";

import type {
  OrganizerScanner,
  ScannerStatus,
} from "@/features/organizers/scanners";

import {
  isAssignableScanner,
  isCurrentAssignment,
} from "./OrganizerEventScannerAssignments";

function scanner(
  status: ScannerStatus,
  archivedAt: string | null = null,
): OrganizerScanner {
  return {
    status,
    archived_at: archivedAt,
  } as OrganizerScanner;
}

describe("scanner assignment eligibility", () => {
  it.each<ScannerStatus>([
    "INVITED",
    "EMAIL_SENT",
    "OPENED",
    "ACTIVE",
  ])(
    "accepte le statut %s",
    (status) => {
      expect(
        isAssignableScanner(
          scanner(status),
        ),
      ).toBe(true);
    },
  );

  it.each<ScannerStatus>([
    "LEAVE_REQUESTED",
    "INVITATION_CANCELLED",
    "DELETED",
  ])(
    "masque le statut %s",
    (status) => {
      expect(
        isAssignableScanner(
          scanner(status),
        ),
      ).toBe(false);
    },
  );

  it(
    "masque un scanner actif archivé",
    () => {
      expect(
        isAssignableScanner(
          scanner(
            "ACTIVE",
            "2026-09-01T16:00:00Z",
          ),
        ),
      ).toBe(false);
    },
  );

  it.each<ScannerStatus>([
    "INVITATION_CANCELLED",
    "DELETED",
  ])(
    "masque une affectation terminale de la liste courante: %s",
    (status) => {
      expect(
        isCurrentAssignment({
          status,
        }),
      ).toBe(false);
    },
  );

  it.each<ScannerStatus>([
    "INVITED",
    "EMAIL_SENT",
    "OPENED",
    "ACTIVE",
    "LEAVE_REQUESTED",
  ])(
    "conserve une affectation non terminale dans la liste courante: %s",
    (status) => {
      expect(
        isCurrentAssignment({
          status,
        }),
      ).toBe(true);
    },
  );

});
