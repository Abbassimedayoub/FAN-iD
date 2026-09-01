import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AuthProvider, useAuth } from "./AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";
import type { AuthUser, UserRole } from "./types";

function userWithRole(role: UserRole): AuthUser {
  return {
    id: "77d350dd-aee8-4c26-b4a0-07b3b1fde10a",
    email: `${role.toLowerCase()}@example.test`,
    first_name: "Test",
    last_name: "User",
    role,
    created_at: "2026-08-20T12:00:00Z",
  };
}

function renderAdminRoute(user: AuthUser | null) {
  return render(
    <MemoryRouter initialEntries={["/admin/organizers"]}>
      <AuthProvider initialUser={user}>
        <Routes>
          <Route path="/login" element={<h1>Connexion</h1>} />
          <Route path="/forbidden" element={<h1>Accès refusé</h1>} />
          <Route
            path="/admin/organizers"
            element={
              <ProtectedRoute allowedRoles={["ADMIN"]}>
                <h1>Administration des organisateurs</h1>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("redirects an unauthenticated visitor to login", () => {
    renderAdminRoute(null);

    expect(screen.getByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  });

  it.each(["FAN", "ORGANIZER", "SCANNER"] as const)(
    "refuses the ADMIN route to role %s",
    (role) => {
      renderAdminRoute(userWithRole(role));

      expect(screen.getByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
    },
  );

  it("allows ADMIN to reach the administration route", () => {
    renderAdminRoute(userWithRole("ADMIN"));

    expect(
      screen.getByRole("heading", { name: "Administration des organisateurs" }),
    ).toBeInTheDocument();
  });

  it("allows an ORGANIZER route only to ORGANIZER", () => {
    render(
      <MemoryRouter initialEntries={["/organizer"]}>
        <AuthProvider initialUser={userWithRole("ORGANIZER")}>
          <Routes>
            <Route
              path="/organizer"
              element={
                <ProtectedRoute allowedRoles={["ORGANIZER"]}>
                  <h1>Espace organisateur</h1>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Espace organisateur" })).toBeInTheDocument();
  });
});

function AuthProbe({ children }: { children?: ReactNode }) {
  const { user, authenticate } = useAuth();

  return (
    <>
      <p>{user?.role ?? "anonymous"}</p>
      <button type="button" onClick={() => authenticate(userWithRole("ADMIN"))}>
        Authentifier
      </button>
      {children}
    </>
  );
}

describe("AuthProvider", () => {
  it("updates the authenticated principal in memory", () => {
    render(
      <AuthProvider initialUser={null}>
        <AuthProbe />
      </AuthProvider>,
    );

    expect(screen.getByText("anonymous")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Authentifier" }));

    expect(screen.getByText("ADMIN")).toBeInTheDocument();
  });

  it("fails closed when useAuth is called outside AuthProvider", () => {
    expect(() => render(<AuthProbe />)).toThrow("useAuth doit être utilisé dans AuthProvider.");
  });
});
