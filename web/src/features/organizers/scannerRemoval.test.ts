import { beforeEach, describe, expect, it, vi } from "vitest";

import { httpClient } from "@/lib/httpClient";
import {
  type OrganizerScanner,
  requestOrganizerScannerSecurityCode,
  revokeOrganizerScanner,
} from "./scanners";

vi.mock("@/lib/httpClient", () => ({
  httpClient: {
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("scanner removal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const scanner: OrganizerScanner = {
    id: "scanner-1",
    user_id: "user-1",
    first_name: "Amine",
    last_name: "Scanner",
    email: "amine@example.test",
    status: "EMAIL_SENT",
    scanner_email_sent_at: null,
    organizer_email_sent_at: null,
    opened_at: null,
    activated_at: null,
    removed_at: null,
    archived_at: null,
    created_at: "2026-08-27T00:00:00Z",
    updated_at: "2026-08-27T00:00:00Z",
    version: 3,
  };

  it("demande un challenge OTP pour le retrait", async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      data: {
        challenge_id: "challenge-1",
        expires_in_seconds: 300,
      },
    } as never);

    const result = await requestOrganizerScannerSecurityCode(scanner, "REVOKE");

    expect(httpClient.post).toHaveBeenCalledWith(
      "/api/v1/organizers/me/scanners/scanner-1/security-code",
      {
        action: "REVOKE",
      },
    );

    expect(result).toEqual({
      challenge_id: "challenge-1",
      expires_in_seconds: 300,
    });
  });

  it("envoie DELETE avec OTP et If-Match", async () => {
    vi.mocked(httpClient.delete).mockResolvedValue({
      data: undefined,
    });

    await revokeOrganizerScanner(scanner, {
      challenge_id: "challenge-1",
      code: "123456",
    });

    expect(httpClient.delete).toHaveBeenCalledWith("/api/v1/organizers/me/scanners/scanner-1", {
      data: {
        challenge_id: "challenge-1",
        code: "123456",
      },
      headers: {
        "If-Match": '"3"',
      },
    });
  });
});
