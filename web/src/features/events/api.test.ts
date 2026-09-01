import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { cancelEvent, postponeEvent, suspendEvent, unarchiveEvent } from "./api";
import type { OrganizerEvent } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const event: OrganizerEvent = {
  id: "event-1",
  organizer_id: "org-1",
  category_id: "football",
  name: "Derby",
  description: "",
  starts_at: "2026-09-20T18:00:00Z",
  ends_at: "2026-09-20T21:00:00Z",
  postponed_from_starts_at: null,
  postponed_from_ends_at: null,
  postponed_to_starts_at: null,
  postponed_to_ends_at: null,
  venue: "Stade",
  capacity_total: 1000,
  image_url: null,
  status: "PUBLISHED",
  published_at: "2026-08-25T20:00:00Z",
  lifecycle_reason: "",
  lifecycle_changed_at: null,
  version: 7,
  created_at: "2026-08-25T19:00:00Z",
  updated_at: "2026-08-25T20:00:00Z",
};

function response(config: InternalAxiosRequestConfig): AxiosResponse<OrganizerEvent> {
  return {
    config,
    data: event,
    headers: new AxiosHeaders(),
    status: 200,
    statusText: "OK",
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("envoie If-Match sur les trois transitions de cycle de vie", async () => {
  const calls: InternalAxiosRequestConfig[] = [];

  httpClient.defaults.adapter = async (config) => {
    calls.push(config);

    return response(config);
  };

  await postponeEvent(event, {
    starts_at: "2026-09-27T18:00:00Z",
    ends_at: "2026-09-27T21:00:00Z",
    reason: "Report",
    notify_buyers: true,
  });

  await suspendEvent(event, {
    reason: "Suspension",
    notify_buyers: true,
  });

  await cancelEvent(event, {
    reason: "Annulation",
    notify_buyers: true,
    refund_requested: true,
  });

  expect(calls.map((call) => call.url)).toEqual([
    "/api/v1/events/event-1/postpone",
    "/api/v1/events/event-1/suspend",
    "/api/v1/events/event-1/cancel",
  ]);

  expect(calls.every((call) => call.headers.get("If-Match") === '"7"')).toBe(true);
});

it("désarchive avec If-Match", async () => {
  let requestUrl = "";
  let ifMatch = "";

  httpClient.defaults.adapter = async (config) => {
    requestUrl = config.url ?? "";

    ifMatch = String(config.headers.get("If-Match") ?? "");

    return response(config);
  };

  await unarchiveEvent({
    ...event,
    status: "ARCHIVED",
  });

  expect(requestUrl).toBe("/api/v1/events/event-1/unarchive");

  expect(ifMatch).toBe('"7"');
});
