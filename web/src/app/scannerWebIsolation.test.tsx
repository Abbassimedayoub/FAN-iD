import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider } from "@/features/auth/AuthContext";
import type { AuthUser } from "@/features/auth/types";

import { AppRoutes } from "./router";

const scanner: AuthUser = {
  id: "scanner-web-isolation",
  email: "scanner@example.test",
  first_name: "Samir",
  last_name: "Scanner",
  role: "SCANNER",
  created_at: "2026-09-01T08:00:00Z",
};

function renderScannerAt(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider initialUser={scanner}>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("isolation web du rôle SCANNER", () => {
  it.each(["/", "/scanner", "/sessions", "/organizer", "/organizer/events", "/organizer/scanners"])(
    "refuse au scanner l’accès web à %s",
    async (path) => {
      renderScannerAt(path);

      expect(
        await screen.findByRole("heading", {
          name: "Accès refusé",
        }),
      ).toBeInTheDocument();
    },
  );
});
