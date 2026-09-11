import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { AdminFinancialDashboardPage } from "./AdminFinancialDashboardPage";
import type { AdminFinancialDashboard } from "./types";

const originalAdapter = httpClient.defaults.adapter;

function response<T>(config: InternalAxiosRequestConfig, data: T): AxiosResponse<T> {
  return {
    config,
    data,
    headers: {},
    status: 200,
    statusText: "OK",
  };
}

function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
    },
  });
}

function renderPage(queryClient = createTestQueryClient()) {
  const result = render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <AdminFinancialDashboardPage />
      </QueryClientProvider>
    </MemoryRouter>,
  );

  return {
    ...result,
    queryClient,
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

describe("AdminFinancialDashboardPage", () => {
  it("renders the financial dashboard returned by the API", async () => {
    const dashboard: AdminFinancialDashboard = {
      confirmed_commission_cents: 12345,
      organizer_count: 2,
      organizers: [
        {
          organizer_id: "00000000-0000-4000-8000-000000000001",
          org_name: "Alpha Events",
          net_revenue_cents: 125000,
          completed_events_count: 2,
        },
        {
          organizer_id: "00000000-0000-4000-8000-000000000002",
          org_name: "Beta Live",
          net_revenue_cents: 75000,
          completed_events_count: 1,
        },
      ],
    };

    const adapter: AxiosAdapter = async (config) => {
      expect(config.url).toBe("/api/v1/admin/dashboard");

      return response(config, dashboard);
    };

    httpClient.defaults.adapter = adapter;

    const { queryClient } = renderPage();

    expect(await screen.findByText("Alpha Events")).toBeInTheDocument();
    expect(screen.getByText("Beta Live")).toBeInTheDocument();
    expect(screen.getByText("Commission FANID confirmée")).toBeInTheDocument();
    expect(screen.getAllByText("Événements finalisés")).toHaveLength(2);

    queryClient.clear();
  });
});
