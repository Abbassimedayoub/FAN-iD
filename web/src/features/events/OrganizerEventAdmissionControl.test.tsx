import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { OrganizerEventAdmissionControl } from "./OrganizerEventAdmissionControl";
import type { OrganizerEvent } from "./types";

const originalAdapter = httpClient.defaults.adapter;

function response(config: InternalAxiosRequestConfig, data: unknown): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status: 200,
    statusText: "OK",
  };
}

function eventFixture(status: OrganizerEvent["status"]): OrganizerEvent {
  return {
    id: "event-admission-1",
    status,
    postponed_to_starts_at: null,
    postponed_to_ends_at: null,
  } as OrganizerEvent;
}

function renderControl(event: OrganizerEvent) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <OrganizerEventAdmissionControl event={event} />
    </QueryClientProvider>,
  );

  return { ...result, queryClient };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("ouvre puis affiche les entrées comme ouvertes", async () => {
  let isOpen = false;
  let openCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (
      config.method === "get" &&
      config.url === "/api/v1/access/events/event-admission-1/admission"
    ) {
      return response(config, { is_open: isOpen });
    }

    if (
      config.method === "post" &&
      config.url === "/api/v1/access/events/event-admission-1/admission/open"
    ) {
      openCalls += 1;
      isOpen = true;
      return response(config, { is_open: true });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderControl(eventFixture("PUBLISHED"));

  expect(
    await screen.findByText("Entrées fermées : aucun billet ne peut être validé par les scanners."),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Ouvrir les entrées" }));

  await waitFor(() => {
    expect(openCalls).toBe(1);
  });
  expect(
    await screen.findByText("Entrées ouvertes : les scanners peuvent valider les billets."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Fermer les entrées" })).toBeInTheDocument();

  queryClient.clear();
});

it("ferme des entrées déjà ouvertes", async () => {
  let isOpen = true;
  let closeCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (
      config.method === "get" &&
      config.url === "/api/v1/access/events/event-admission-1/admission"
    ) {
      return response(config, { is_open: isOpen });
    }

    if (
      config.method === "post" &&
      config.url === "/api/v1/access/events/event-admission-1/admission/close"
    ) {
      closeCalls += 1;
      isOpen = false;
      return response(config, { is_open: false });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderControl(eventFixture("PUBLISHED"));

  expect(
    await screen.findByText("Entrées ouvertes : les scanners peuvent valider les billets."),
  ).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Fermer les entrées" }));

  await waitFor(() => {
    expect(closeCalls).toBe(1);
  });
  expect(
    await screen.findByText("Entrées fermées : aucun billet ne peut être validé par les scanners."),
  ).toBeInTheDocument();

  queryClient.clear();
});

it("interdit l ouverture d un événement reporté sans nouvelle date", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (
      config.method === "get" &&
      config.url === "/api/v1/access/events/event-admission-1/admission"
    ) {
      return response(config, { is_open: false });
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderControl(eventFixture("POSTPONED"));

  expect(
    await screen.findByText(
      "Les entrées ne peuvent pas être ouvertes tant qu’une nouvelle date n’est pas définie.",
    ),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Ouvrir les entrées" })).toBeNull();

  queryClient.clear();
});

it("affiche une erreur explicite si l état des entrées ne peut pas être chargé", async () => {
  httpClient.defaults.adapter = async (config) => {
    if (
      config.method === "get" &&
      config.url === "/api/v1/access/events/event-admission-1/admission"
    ) {
      throw new Error("ADMISSION_STATUS_UNAVAILABLE");
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderControl(eventFixture("PUBLISHED"));

  expect(
    await screen.findByText("Impossible de charger l’état des entrées."),
  ).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Contrôle des entrées" })).toBeInTheDocument();

  queryClient.clear();
});
