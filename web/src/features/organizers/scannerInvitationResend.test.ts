import { beforeEach, describe, expect, it, vi } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { type OrganizerScanner, resendOrganizerScannerInvitation } from "./scanners";

vi.mock("@/lib/httpClient", () => ({
  httpClient: {
    post: vi.fn(),
  },
}));

describe("scanner invitation resend", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls the dedicated resend invitation endpoint", async () => {
    const scanner: OrganizerScanner = {
      id: "scanner-1",
      user_id: "user-1",
      first_name: "Amine",
      last_name: "Scanner",
      email: "amine@example.test",
      status: "OPENED",
      scanner_email_sent_at: null,
      organizer_email_sent_at: null,
      opened_at: null,
      activated_at: null,
      removed_at: null,
      password_help_pending: false,
      password_help_requested_at: null,
      archived_at: null,
    created_at: "2026-08-29T20:00:00Z",
      updated_at: "2026-08-29T21:00:00Z",
      version: 1,
    };

    vi.mocked(httpClient.post).mockResolvedValue({
      data: scanner,
    });

    const result = await resendOrganizerScannerInvitation(scanner);

    expect(result).toEqual(scanner);

    expect(httpClient.post).toHaveBeenCalledWith(
      "/api/v1/organizers/me/scanners/scanner-1/resend-invitation",
      {},
    );
  });
});
