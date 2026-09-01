import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { AxiosHeaders, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { useState } from "react";
import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { OrganizerEventCategoryField } from "./OrganizerEventCategoryField";
import type { EventCategory } from "./types";

const originalAdapter = httpClient.defaults.adapter;

const queryKey = ["catalog", "event-categories"] as const;

function response(config: InternalAxiosRequestConfig, data: unknown, status = 200): AxiosResponse {
  return {
    config,
    data,
    headers: new AxiosHeaders(),
    status,
    statusText: "OK",
  };
}

function CategoryHarness({
  initialCategories,
  initialValue = "",
}: {
  initialCategories: EventCategory[];
  initialValue?: string;
}) {
  const [value, setValue] = useState(initialValue);

  const categoriesQuery = useQuery({
    queryKey,
    queryFn: async () => initialCategories,
    initialData: initialCategories,
    staleTime: Number.POSITIVE_INFINITY,
  });

  return (
    <>
      <OrganizerEventCategoryField
        categories={categoriesQuery.data}
        isPending={categoriesQuery.isPending}
        isError={categoriesQuery.isError}
        value={value}
        onChange={setValue}
      />

      <output data-testid="selected-category">{value}</output>
    </>
  );
}

function renderField(categories: EventCategory[], initialValue = "") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <CategoryHarness initialCategories={categories} initialValue={initialValue} />
    </QueryClientProvider>,
  );

  return {
    ...result,
    queryClient,
  };
}

afterEach(() => {
  httpClient.defaults.adapter = originalAdapter;
});

it("crée une catégorie puis la sélectionne immédiatement", async () => {
  let createdPayload: Record<string, unknown> | null = null;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "post" && config.url === "/api/v1/categories") {
      createdPayload = JSON.parse(String(config.data)) as Record<string, unknown>;

      return response(
        config,
        {
          id: "category-concert",
          name: "Concert",
          description: "",
          version: 1,
          is_owned_by_me: true,
          can_delete: true,
        },
        201,
      );
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderField([
    {
      id: "category-football",
      name: "Football",
      description: "",
      version: 1,
      is_owned_by_me: false,
      can_delete: false,
    },
  ]);

  fireEvent.click(
    screen.getByRole("button", {
      name: "+ Ajouter une catégorie",
    }),
  );

  fireEvent.change(screen.getByLabelText("Nom de la nouvelle catégorie"), {
    target: {
      value: "Concert",
    },
  });

  fireEvent.click(
    screen.getByRole("button", {
      name: "Créer la catégorie",
    }),
  );

  expect(
    await screen.findByRole("option", {
      name: "Concert",
    }),
  ).toBeInTheDocument();

  expect(screen.getByTestId("selected-category")).toHaveTextContent("category-concert");

  expect(
    await screen.findByText("Catégorie « Concert » ajoutée et sélectionnée."),
  ).toBeInTheDocument();

  expect(createdPayload?.["name"]).toBe("Concert");

  queryClient.clear();
});

it("supprime seulement une catégorie personnelle supprimable après confirmation", async () => {
  let deleteCalls = 0;

  httpClient.defaults.adapter = async (config) => {
    if (config.method === "delete" && config.url === "/api/v1/categories/category-custom") {
      deleteCalls += 1;

      return response(config, null, 204);
    }

    throw new Error(`Requête inattendue : ${config.method} ${config.url}`);
  };

  const { queryClient } = renderField(
    [
      {
        id: "category-system",
        name: "Football",
        description: "",
        version: 1,
        is_owned_by_me: false,
        can_delete: false,
      },
      {
        id: "category-custom",
        name: "Mon festival",
        description: "",
        version: 1,
        is_owned_by_me: true,
        can_delete: true,
      },
    ],
    "category-custom",
  );

  expect(
    screen.queryByRole("button", {
      name: "Supprimer la catégorie Football",
    }),
  ).not.toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Supprimer la catégorie Mon festival",
    }),
  );

  expect(
    screen.getByRole("dialog", {
      name: "Supprimer la catégorie ?",
    }),
  ).toBeInTheDocument();

  fireEvent.click(
    screen.getByRole("button", {
      name: "Supprimer définitivement",
    }),
  );

  await waitFor(() => {
    expect(
      screen.queryByRole("option", {
        name: "Mon festival",
      }),
    ).not.toBeInTheDocument();
  });

  expect(deleteCalls).toBe(1);

  expect(screen.getByTestId("selected-category")).toHaveTextContent("");

  expect(await screen.findByText("Catégorie « Mon festival » supprimée.")).toBeInTheDocument();

  queryClient.clear();
});

it("affiche une catégorie personnelle utilisée sans bouton de suppression", () => {
  const { queryClient } = renderField([
    {
      id: "category-used",
      name: "Conférence",
      description: "",
      version: 1,
      is_owned_by_me: true,
      can_delete: false,
    },
  ]);

  expect(screen.getByText("Utilisée par un événement")).toBeInTheDocument();

  expect(
    screen.queryByRole("button", {
      name: "Supprimer la catégorie Conférence",
    }),
  ).not.toBeInTheDocument();

  expect(screen.getByText("Protégée")).toBeInTheDocument();

  queryClient.clear();
});
