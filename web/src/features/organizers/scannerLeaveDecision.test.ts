import { beforeEach, describe, expect, it, vi } from "vitest";

import { httpClient } from "@/lib/httpClient";
import {
  decideOrganizerScannerLeave,
  requestOrganizerScannerSecurityCode,
  type OrganizerScanner,
} from "./scanners";

vi.mock("@/lib/httpClient", () => ({
  httpClient: {
    post: vi.fn(),
  },
}));

describe("decideOrganizerScannerLeave", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const scanner = {
    id: "11111111-1111-4111-8111-111111111111",
    version: 7,
  } as OrganizerScanner;

  it("demande un challenge OTP pour une acceptation", async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      data: {
        challenge_id: "challenge-leave",
        expires_in_seconds: 300,
      },
    } as never);

    const result = await requestOrganizerScannerSecurityCode(scanner, "LEAVE_ACCEPT");

    expect(httpClient.post).toHaveBeenCalledWith(
      `/api/v1/organizers/me/scanners/${scanner.id}/security-code`,
      {
        action: "LEAVE_ACCEPT",
      },
    );

    expect(result).toEqual({
      challenge_id: "challenge-leave",
      expires_in_seconds: 300,
    });
  });

  it("envoie une acceptation avec OTP et If-Match", async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      data: undefined,
    } as never);

    await decideOrganizerScannerLeave(scanner, "ACCEPT", {
      challenge_id: "challenge-leave",
      code: "654321",
    });

    expect(httpClient.post).toHaveBeenCalledWith(
      `/api/v1/organizers/me/scanners/${scanner.id}/leave-request`,
      {
        decision: "ACCEPT",
        challenge_id: "challenge-leave",
        code: "654321",
      },
      {
        headers: {
          "If-Match": '"7"',
        },
      },
    );
  });

  it("envoie un refus sans OTP avec If-Match", async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      data: undefined,
    } as never);

    await decideOrganizerScannerLeave(scanner, "REJECT");

    expect(httpClient.post).toHaveBeenCalledWith(
      `/api/v1/organizers/me/scanners/${scanner.id}/leave-request`,
      {
        decision: "REJECT",
      },
      {
        headers: {
          "If-Match": '"7"',
        },
      },
    );
  });
});
