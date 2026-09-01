import { afterEach, expect, it } from "vitest";

import { httpClient } from "@/lib/httpClient";

import { eventImageUrl } from "./eventImageUrl";

const originalBaseURL = httpClient.defaults.baseURL;

afterEach(() => {
  httpClient.defaults.baseURL = originalBaseURL;
});

it("transforme une URL locale API relative en URL absolue backend", () => {
  httpClient.defaults.baseURL = "http://127.0.0.1:8000";

  expect(eventImageUrl("/api/v1/storage/local/signed-token")).toBe(
    "http://127.0.0.1:8000/api/v1/storage/local/signed-token",
  );
});

it("conserve une URL objet storage déjà absolue", () => {
  const value = "https://storage.example.test/events/poster.png";

  expect(eventImageUrl(value)).toBe(value);
});

it("conserve une preview blob locale", () => {
  expect(eventImageUrl("blob:http://localhost/test")).toBe("blob:http://localhost/test");
});

it("retourne null sans image", () => {
  expect(eventImageUrl(null)).toBeNull();
});
