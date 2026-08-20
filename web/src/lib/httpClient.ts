/**
 * Client HTTP Web FAN id.
 *
 * Invariants de sécurité :
 * - access token uniquement en mémoire ;
 * - refresh uniquement dans le cookie HttpOnly ;
 * - credentials envoyés avec les requêtes navigateur ;
 * - un seul refresh réseau pour N réponses 401 concurrentes ;
 * - une requête n'est rejouée qu'une seule fois ;
 * - un échec du endpoint de refresh ne déclenche jamais un refresh récursif.
 */
import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { toAppError } from "./errors";

const CORRELATION_HEADER = "X-Correlation-ID";
const API_BASE_URL = import.meta.env["VITE_API_URL"] ?? "http://localhost:8000";

interface AuthRequestConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
  _skipAuthRefresh?: boolean;
}

interface RefreshResponse {
  access: string;
}

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;

function generateCorrelationId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token && token.length > 0 ? token : null;
}

export function clearAccessToken(): void {
  accessToken = null;
}

export const httpClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  withCredentials: true,
});

httpClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const authConfig = config as AuthRequestConfig;

  config.headers.set(CORRELATION_HEADER, generateCorrelationId());

  if (!authConfig._skipAuthRefresh) {
    const token = getAccessToken();
    if (token) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
  }

  return config;
});

async function performTokenRefresh(): Promise<string> {
  const config = {
    withCredentials: true,
    _skipAuthRefresh: true,
  } as AxiosRequestConfig & { _skipAuthRefresh: true };

  const response = await httpClient.post<RefreshResponse>(
    "/api/v1/auth/token/refresh",
    { client: "web" },
    config,
  );

  const token = response.data?.access;

  if (typeof token !== "string" || token.length === 0) {
    throw new Error("Réponse de refresh invalide : access token absent");
  }

  setAccessToken(token);
  return token;
}

async function refreshAccessTokenOnce(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = performTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as AuthRequestConfig | undefined;

    if (original?._skipAuthRefresh) {
      return Promise.reject(toAppError(error));
    }

    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;

      try {
        const newToken = await refreshAccessTokenOnce();
        original.headers.set("Authorization", `Bearer ${newToken}`);
        return httpClient(original);
      } catch {
        clearAccessToken();
      }
    }

    return Promise.reject(toAppError(error));
  },
);
