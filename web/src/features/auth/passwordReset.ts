import type { AxiosRequestConfig } from "axios";

import { clearAccessToken, httpClient } from "@/lib/httpClient";

interface PublicAuthRequestConfig extends AxiosRequestConfig {
  _skipAuthRefresh: true;
}

function publicAuthConfig(): PublicAuthRequestConfig {
  return {
    _skipAuthRefresh: true,
  };
}

export interface PasswordResetRequestResponse {
  message: string;
  expires_in_seconds: number;
}

export interface PasswordResetByTokenPayload {
  token: string;
  new_password: string;
}

export interface PasswordResetByCodePayload {
  email: string;
  code: string;
  new_password: string;
}

export async function requestPasswordReset(email: string): Promise<PasswordResetRequestResponse> {
  const response = await httpClient.post<PasswordResetRequestResponse>(
    "/api/v1/auth/password/reset/request",
    {
      email: email.trim(),
    },
    publicAuthConfig(),
  );

  const data = response.data;

  if (typeof data?.message !== "string" || typeof data?.expires_in_seconds !== "number") {
    throw new Error("Réponse de récupération invalide.");
  }

  return data;
}

export async function confirmPasswordReset(
  payload: PasswordResetByTokenPayload | PasswordResetByCodePayload,
): Promise<void> {
  await httpClient.post("/api/v1/auth/password/reset/confirm", payload, publicAuthConfig());

  clearAccessToken();
}
