import { httpClient } from "@/lib/httpClient";

import { USER_ROLES, type AuthUser, type UserRole } from "./types";

function isAuthUser(value: unknown): value is AuthUser {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const user = value as Record<string, unknown>;

  return (
    typeof user["id"] === "string" &&
    typeof user["email"] === "string" &&
    typeof user["first_name"] === "string" &&
    typeof user["last_name"] === "string" &&
    typeof user["created_at"] === "string" &&
    typeof user["role"] === "string" &&
    USER_ROLES.includes(user["role"] as UserRole)
  );
}

export async function getCurrentUser(): Promise<AuthUser> {
  const response = await httpClient.get<unknown>("/api/v1/auth/me");

  if (!isAuthUser(response.data)) {
    throw new Error("Réponse /auth/me invalide.");
  }

  return response.data;
}
