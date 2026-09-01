import { beforeEach, describe, expect, it, vi } from "vitest";

import { httpClient } from "@/lib/httpClient";

import {
  fetchOrganizerScanners,
  fetchOrganizerArchivedScannersPage,
  fetchOrganizerScannersPage,
  inviteOrganizerScanner,
} from "./scanners";

vi.mock("@/lib/httpClient", () => ({
  httpClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe("organizer scanners api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists scanners for the connected organizer", async () => {
    vi.mocked(httpClient.get).mockResolvedValue({
      data: [
        {
          id: "scanner-1",
          user_id: "user-1",
          first_name: "Amine",
          last_name: "Scanner",
          email: "amine@example.test",
          status: "EMAIL_SENT",
          scanner_email_sent_at: "2026-08-26T20:00:00Z",
          organizer_email_sent_at: "2026-08-26T20:00:01Z",
          opened_at: null,
          activated_at: null,
          removed_at: null,
          created_at: "2026-08-26T19:59:00Z",
          updated_at: "2026-08-26T20:00:01Z",
          version: 1,
        },
      ],
    });

    const scanners = await fetchOrganizerScanners();

    expect(httpClient.get).toHaveBeenCalledWith("/api/v1/organizers/me/scanners", {
      params: {
        page: 1,
      },
    });

    expect(scanners).toHaveLength(1);
    expect(scanners[0]?.status).toBe("EMAIL_SENT");
  });

  it("sends page, trimmed search and status for paginated listing", async () => {
    vi.mocked(httpClient.get).mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [],
      },
    });

    await fetchOrganizerScannersPage({
      page: 2,
      search: "  Nadia  ",
      status: "ACTIVE",
    });

    expect(httpClient.get).toHaveBeenCalledWith("/api/v1/organizers/me/scanners", {
      params: {
        page: 2,
        search: "Nadia",
        status: "ACTIVE",
      },
    });
  });

  it("sends page, search and terminal status for archived scanners", async () => {
    vi.mocked(httpClient.get).mockResolvedValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [],
      },
    });

    await fetchOrganizerArchivedScannersPage({
      page: 3,
      search: "  Leila  ",
      status: "DELETED",
    });

    expect(httpClient.get).toHaveBeenCalledWith("/api/v1/organizers/me/scanners/archived", {
      params: {
        page: 3,
        search: "Leila",
        status: "DELETED",
      },
    });
  });

  it("trims invitation fields before sending them", async () => {
    vi.mocked(httpClient.post).mockResolvedValue({
      data: {
        id: "scanner-1",
        user_id: "user-1",
        first_name: "Amine",
        last_name: "Scanner",
        email: "amine@example.test",
        status: "INVITED",
        scanner_email_sent_at: null,
        organizer_email_sent_at: null,
        opened_at: null,
        activated_at: null,
        removed_at: null,
        created_at: "2026-08-26T19:59:00Z",
        updated_at: "2026-08-26T19:59:00Z",
        version: 1,
      },
    });

    await inviteOrganizerScanner({
      first_name: "  Amine ",
      last_name: " Scanner  ",
      email: " amine@example.test ",
    });

    expect(httpClient.post).toHaveBeenCalledWith("/api/v1/organizers/me/scanners", {
      first_name: "Amine",
      last_name: "Scanner",
      email: "amine@example.test",
    });
  });
});
