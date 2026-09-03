import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { AdminOrganizerDetailView } from "./AdminOrganizerDetailView";
import type { Organizer } from "./types";

const organizer: Organizer = {
  id: "00000000-0000-4000-8000-000000000001",
  org_name: "Association Lumière",
  validation_status: "PENDING",
  commission_rate: "0.0000",
  vat_number: null,
  contact_email: "contact@example.test",
  rejection_reason: null,
  validated_at: null,
  version: 1,
  created_at: "2026-09-03T10:00:00Z",
  updated_at: "2026-09-03T10:00:00Z",
};

it("ne propose plus une approbation manuelle du dossier pending", () => {
  render(
    <AdminOrganizerDetailView
      data={organizer}
      isPending={false}
      isFetching={false}
      error={null}
      onRetry={vi.fn()}
      onBack={vi.fn()}
      actions={{
        isPending: false,
        feedback: null,
        isStaleResource: false,
        onReject: vi.fn(async () => true),
        onSuspend: vi.fn(async () => true),
        onReloadStale: vi.fn(),
      }}
    />,
  );

  expect(
    screen.queryByRole("button", {
      name: "Approuver",
    }),
  ).not.toBeInTheDocument();

  expect(
    screen.getByRole("button", {
      name: "Rejeter",
    }),
  ).toBeInTheDocument();
});
