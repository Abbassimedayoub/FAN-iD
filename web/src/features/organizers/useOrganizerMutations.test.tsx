import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import type { PropsWithChildren } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import type { Organizer, OrganizerPage } from "./types";
import {
  useApproveOrganizer,
  useRejectOrganizer,
  useSuspendOrganizer,
} from "./useOrganizerMutations";
import { organizerQueryKeys } from "./useOrganizers";

const originalAdapter = httpClient.defaults.adapter;

const ORGANIZER_ID = "00000000-0000-4000-8000-000000000001";

const organizer: Organizer = {
  id: ORGANIZER_ID,
  org_name: "Association Lumière",
  validation_status: "PENDING",
  commission_rate: "0.1000",
  vat_number: null,
  contact_email: "contact@example.test",
  rejection_reason: null,
  validated_at: null,
  version: 4,
  created_at: "2026-08-20T10:00:00Z",
  updated_at: "2026-08-20T10:00:00Z",
};

const organizerPage: OrganizerPage = {
  count: 1,
  next: null,
  previous: null,
  results: [organizer],
};

function response<T>(
  config: InternalAxiosRequestConfig,
  status: number,
  data: T,
): AxiosResponse<T> {
  return {
    config,
    data,
    headers: {},
    status,
    statusText: String(status),
  };
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function seedCaches(queryClient: QueryClient) {
  const listKey = organizerQueryKeys.list({
    page: 1,
    validationStatus: undefined,
  });
  const detailKey = organizerQueryKeys.detail(ORGANIZER_ID);

  queryClient.setQueryData(listKey, organizerPage);
  queryClient.setQueryData(detailKey, organizer);

  return {
    listKey,
    detailKey,
  };
}

function expectSuccessfulCacheUpdate(
  queryClient: QueryClient,
  listKey: ReturnType<typeof organizerQueryKeys.list>,
  detailKey: ReturnType<typeof organizerQueryKeys.detail>,
  expected: Organizer,
) {
  expect(queryClient.getQueryData(detailKey)).toEqual(expected);
  expect(queryClient.getQueryState(detailKey)?.isInvalidated).toBe(false);
  expect(queryClient.getQueryState(listKey)?.isInvalidated).toBe(true);
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

describe("organizer admin mutation hooks", () => {
  it("approuve puis met à jour la fiche et invalide seulement les listes", async () => {
    const updated: Organizer = {
      ...organizer,
      validation_status: "APPROVED",
      version: 5,
    };

    const adapter: AxiosAdapter = async (config) => response(config, 200, updated);
    httpClient.defaults.adapter = adapter;

    const queryClient = createQueryClient();
    const { listKey, detailKey } = seedCaches(queryClient);

    const { result } = renderHook(() => useApproveOrganizer(), {
      wrapper: createWrapper(queryClient),
    });

    act(() => {
      result.current.mutate({
        organizerId: ORGANIZER_ID,
        version: 4,
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expectSuccessfulCacheUpdate(queryClient, listKey, detailKey, updated);
  });

  it("rejette puis met à jour la fiche et invalide seulement les listes", async () => {
    const updated: Organizer = {
      ...organizer,
      validation_status: "REJECTED",
      rejection_reason: "Dossier incomplet",
      version: 5,
    };

    const adapter: AxiosAdapter = async (config) => response(config, 200, updated);
    httpClient.defaults.adapter = adapter;

    const queryClient = createQueryClient();
    const { listKey, detailKey } = seedCaches(queryClient);

    const { result } = renderHook(() => useRejectOrganizer(), {
      wrapper: createWrapper(queryClient),
    });

    act(() => {
      result.current.mutate({
        organizerId: ORGANIZER_ID,
        version: 4,
        reason: "Dossier incomplet",
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expectSuccessfulCacheUpdate(queryClient, listKey, detailKey, updated);
  });

  it("suspend puis met à jour la fiche et invalide seulement les listes", async () => {
    const approved: Organizer = {
      ...organizer,
      validation_status: "APPROVED",
      version: 7,
    };
    const updated: Organizer = {
      ...approved,
      validation_status: "SUSPENDED",
      version: 8,
    };

    const adapter: AxiosAdapter = async (config) => response(config, 200, updated);
    httpClient.defaults.adapter = adapter;

    const queryClient = createQueryClient();
    const listKey = organizerQueryKeys.list({
      page: 1,
      validationStatus: "APPROVED",
    });
    const detailKey = organizerQueryKeys.detail(ORGANIZER_ID);

    queryClient.setQueryData(listKey, {
      ...organizerPage,
      results: [approved],
    });
    queryClient.setQueryData(detailKey, approved);

    const { result } = renderHook(() => useSuspendOrganizer(), {
      wrapper: createWrapper(queryClient),
    });

    act(() => {
      result.current.mutate({
        organizerId: ORGANIZER_ID,
        version: 7,
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expectSuccessfulCacheUpdate(queryClient, listKey, detailKey, updated);
  });
});
