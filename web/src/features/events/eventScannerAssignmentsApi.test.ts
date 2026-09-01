import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { assignEventScanner, fetchEventScannerAssignments, unassignEventScanner } from "./api";
import type { EventScannerAssignment } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const assignment: EventScannerAssignment = {
  assignment_id: "assignment-1",
  scanner_id: "scanner-1",
  first_name: "Amine",
  last_name: "Scanner",
  email: "amine@example.test",
  status: "EMAIL_SENT",
  scanner_version: 2,
  assigned_at: "2026-08-30T18:00:00Z",
};

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("utilise les routes event-scoped pour lister, affecter et retirer", async () => {
  const calls: InternalAxiosRequestConfig[] = [];

  httpClient.defaults.adapter = async (config) => {
    calls.push(config);

    return {
      config,
      data: config.method === "get" ? [assignment] : assignment,
      headers: new AxiosHeaders(),
      status: config.method === "post" ? 201 : config.method === "delete" ? 204 : 200,
      statusText: "OK",
    } as AxiosResponse;
  };

  const listed = await fetchEventScannerAssignments("event-1");

  const created = await assignEventScanner("event-1", "scanner-1");

  await unassignEventScanner("event-1", "scanner-1");

  expect(listed).toEqual([assignment]);

  expect(created).toEqual(assignment);

  expect(calls.map((call) => [call.method, call.url])).toEqual([
    ["get", "/api/v1/events/event-1/scanners"],
    ["post", "/api/v1/events/event-1/scanners"],
    ["delete", "/api/v1/events/event-1/scanners/scanner-1"],
  ]);

  const requestData = calls[1]?.data;

  expect(typeof requestData === "string" ? JSON.parse(requestData) : requestData).toEqual({
    scanner_id: "scanner-1",
  });
});
