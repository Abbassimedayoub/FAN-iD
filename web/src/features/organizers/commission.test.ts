import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import {
  acceptAdminCommissionProposal,
  acceptMyCommissionProposal,
  commissionPercentToRate,
  createAdminCommissionProposal,
  createMyCommissionProposal,
  fetchAdminCommissionNegotiation,
  fetchMyCommissionNegotiation,
} from "./commission";

const originalAdapter = httpClient.defaults.adapter;
const ORGANIZER_ID = "00000000-0000-4000-8000-000000000001";

function response(config: InternalAxiosRequestConfig, data: unknown, status = 200): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: "OK",
  };
}

function negotiation(version: number) {
  return {
    organizer_id: ORGANIZER_ID,
    validation_status: "APPROVED",
    commission_status: "NEGOTIATING",
    agreed_rate: null,
    agreed_at: null,
    version,
    proposals: [],
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

describe("commission API", () => {
  it("convertit un pourcentage UI vers le taux décimal backend", () => {
    expect(commissionPercentToRate("12")).toBe("0.1200");
    expect(commissionPercentToRate("8.5")).toBe("0.0850");
    expect(commissionPercentToRate("0")).toBe("0.0000");
    expect(commissionPercentToRate("100")).toBe("1.0000");
  });

  it("utilise les trois routes Organizer avec If-Match", async () => {
    const calls: InternalAxiosRequestConfig[] = [];

    httpClient.defaults.adapter = async (config) => {
      calls.push(config);
      return response(config, negotiation(5));
    };

    await fetchMyCommissionNegotiation();
    await createMyCommissionProposal(4, "0.0850");
    await acceptMyCommissionProposal(5);

    expect(calls.map((call) => [call.method, call.url])).toEqual([
      ["get", "/api/v1/organizers/me/commission-negotiation"],
      ["post", "/api/v1/organizers/me/commission-proposals"],
      ["post", "/api/v1/organizers/me/commission-accept"],
    ]);

    expect(calls[1]?.headers.get("If-Match")).toBe('"4"');
    expect(calls[2]?.headers.get("If-Match")).toBe('"5"');

    const proposalBody = calls[1]?.data;

    expect(typeof proposalBody === "string" ? JSON.parse(proposalBody) : proposalBody).toEqual({
      commission_rate: "0.0850",
    });
  });

  it("utilise les trois routes Admin avec If-Match", async () => {
    const calls: InternalAxiosRequestConfig[] = [];

    httpClient.defaults.adapter = async (config) => {
      calls.push(config);
      return response(config, negotiation(8));
    };

    await fetchAdminCommissionNegotiation(ORGANIZER_ID);
    await createAdminCommissionProposal(ORGANIZER_ID, 7, "0.0800");
    await acceptAdminCommissionProposal(ORGANIZER_ID, 8);

    expect(calls.map((call) => [call.method, call.url])).toEqual([
      ["get", `/api/v1/admin/organizers/${ORGANIZER_ID}/commission-negotiation`],
      ["post", `/api/v1/admin/organizers/${ORGANIZER_ID}/commission-proposals`],
      ["post", `/api/v1/admin/organizers/${ORGANIZER_ID}/commission-accept`],
    ]);

    expect(calls[1]?.headers.get("If-Match")).toBe('"7"');
    expect(calls[2]?.headers.get("If-Match")).toBe('"8"');
  });
});
