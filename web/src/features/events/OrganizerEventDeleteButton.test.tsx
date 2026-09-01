import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, expect, it, vi } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { OrganizerEventDeleteButton } from "./OrganizerEventDeleteButton";
import type { OrganizerEvent } from "./types";

const originalAdapter = httpClient.defaults.adapter;

function response(config: InternalAxiosRequestConfig, data: unknown, status = 200): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: status === 204 ? "No Content" : "OK",
  };
}

const draft = {
  id: "event-delete-1",
  organizer_id: "org-1",
  category_id: "football",
  name: "Brouillon à supprimer",
  description: "Test",
  starts_at: "2026-09-20T18:00:00Z",
  ends_at: "2026-09-20T21:00:00Z",
  venue: "Stade FANID",
  capacity_total: 100,
  image_url: null,
  status: "DRAFT",
  published_at: null,
  lifecycle_reason: "",
  lifecycle_changed_at: null,
  version: 7,
  created_at: "2026-08-26T20:00:00Z",
  updated_at: "2026-08-26T20:00:00Z",
} as OrganizerEvent;

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("confirme puis supprime un brouillon avec If-Match", async () => {
  let request: InternalAxiosRequestConfig | null = null;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "delete" && config.url === "/api/v1/events/event-delete-1") {
      request = config;

      return response(config, null, 204);
    }

    throw new Error(`Unexpected ${config.method} ${config.url}`);
  };

  const onDeleted = vi.fn().mockResolvedValue(undefined);

  render(<OrganizerEventDeleteButton event={draft} onDeleted={onDeleted} />);

  fireEvent.click(
    screen.getByRole("button", {
      name: "Supprimer définitivement",
    }),
  );

  const dialog = await screen.findByRole("dialog", {
    name: "Supprimer définitivement",
  });

  expect(dialog).toBeInTheDocument();

  expect(screen.getByText("Cette action est irréversible.")).toBeInTheDocument();

  fireEvent.click(
    within(dialog).getByRole("button", {
      name: "Supprimer définitivement",
    }),
  );

  await waitFor(() => {
    expect(onDeleted).toHaveBeenCalledTimes(1);
  });

  expect(request).not.toBeNull();

  const headers = AxiosHeaders.from(request!.headers);

  expect(headers.get("If-Match")).toBe('"7"');
});

it("ne propose pas la suppression hors brouillon", () => {
  render(
    <OrganizerEventDeleteButton
      event={{
        ...draft,
        status: "PUBLISHED",
      }}
      onDeleted={() => undefined}
    />,
  );

  expect(
    screen.queryByRole("button", {
      name: "Supprimer définitivement",
    }),
  ).not.toBeInTheDocument();
});
