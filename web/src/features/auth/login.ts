import type { AxiosRequestConfig } from "axios";

import { clearAccessToken, httpClient, setAccessToken } from "@/lib/httpClient";

import type { LoginResponse } from "./types";

export interface LoginCredentials {
  email: string;
  password: string;
}

export async function loginWeb(credentials: LoginCredentials): Promise<LoginResponse> {
  clearAccessToken();

  const config = {
    withCredentials: true,
    _skipAuthRefresh: true,
  } as AxiosRequestConfig & { _skipAuthRefresh: true };

  const response = await httpClient.post<LoginResponse>(
    "/api/v1/auth/login",
    {
      email: credentials.email,
      password: credentials.password,
      client: "web",
    },
    config,
  );

  if (typeof response.data.access !== "string" || response.data.access.length === 0) {
    throw new Error("Réponse de connexion invalide : access token absent");
  }

  setAccessToken(response.data.access);

  return response.data;
}
