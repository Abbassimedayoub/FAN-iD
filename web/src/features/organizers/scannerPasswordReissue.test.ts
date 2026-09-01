import { beforeEach, describe, expect, it, vi } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { type OrganizerScanner, reissueOrganizerScannerPassword } from "./scanners";

vi.mock("@/lib/httpClient", () => ({
  httpClient: {
    post: vi.fn(),
  },
}));

describe("scanner password reissue", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls the temporary password endpoint", async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      data: {},
    });

    const scanner: OrganizerScanner = {
      id: "scanner-1",
      user_id: "user-1",
      first_name: "Amine",
      last_name: "Scanner",
      email: "amine@example.test",
      status: "ACTIVE",
      scanner_email_sent_at: null,
      organizer_email_sent_at: null,
      opened_at: null,
      activated_at: null,
      removed_at: null,
      password_help_pending: true,
      password_help_requested_at: "2026-08-29T22:00:00Z",
      archived_at: null,
    created_at: "2026-08-29T20:00:00Z",
      updated_at: "2026-08-29T22:00:00Z",
      version: 4,
    };

    await reissueOrganizerScannerPassword(scanner);

    expect(httpClient.post).toHaveBeenCalledWith(
      "/api/v1/organizers/me/scanners/scanner-1/temporary-password",
      {},
    );
  });
});
