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
const REFRESH_URL = "/api/v1/auth/token/refresh";

export const AUTH_SESSION_INVALIDATED_EVENT = "fanid:auth-session-invalidated";

const EXPLICIT_INVALID_SESSION_CODES = new Set([
  "TOKEN_INVALID",
  "TOKEN_REUSE_DETECTED",
  "DEVICE_MISMATCH",
  "NOT_AUTHENTICATED",
  "SESSION_INVALID",
  "SESSION_REVOKED",
]);

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

function apiErrorCode(error: AxiosError): string | null {
  const data = error.response?.data;

  if (typeof data !== "object" || data === null || !("error" in data)) {
    return null;
  }

  const apiError = (data as { error?: unknown }).error;

  if (typeof apiError !== "object" || apiError === null || !("code" in apiError)) {
    return null;
  }

  const code = (apiError as { code?: unknown }).code;
  return typeof code === "string" ? code : null;
}

function isExplicitInvalidSessionResponse(error: AxiosError): boolean {
  return (
    error.response?.status === 403 &&
    EXPLICIT_INVALID_SESSION_CODES.has(apiErrorCode(error) ?? "")
  );
}

function isTransientAppError(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("errorClass" in error)) {
    return false;
  }

  const errorClass = (error as { errorClass?: unknown }).errorClass;
  return errorClass === "network" || errorClass === "server";
}

function notifySessionInvalidated(): void {
  clearAccessToken();

  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_SESSION_INVALIDATED_EVENT));
  }
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

const CROSS_TAB_REFRESH_LOCK_KEY = "fanid_web_refresh_lock";
const CROSS_TAB_REFRESH_LOCK_TTL_MS = 15_000;
const CROSS_TAB_REFRESH_RETRY_MS = 40;

function browserLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function withCrossTabRefreshLock<T>(task: () => Promise<T>): Promise<T> {
  const storage = browserLocalStorage();

  if (!storage) {
    return task();
  }

  const owner = `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  try {
    while (true) {
      const now = Date.now();
      const current = storage.getItem(CROSS_TAB_REFRESH_LOCK_KEY);

      if (current) {
        const separator = current.lastIndexOf("|");
        const expiresAt = Number(current.slice(separator + 1));

        if (Number.isFinite(expiresAt) && expiresAt > now) {
          await delay(CROSS_TAB_REFRESH_RETRY_MS);
          continue;
        }
      }

      storage.setItem(
        CROSS_TAB_REFRESH_LOCK_KEY,
        `${owner}|${now + CROSS_TAB_REFRESH_LOCK_TTL_MS}`,
      );

      await delay(0);

      if (storage.getItem(CROSS_TAB_REFRESH_LOCK_KEY)?.startsWith(`${owner}|`)) {
        break;
      }

      await delay(CROSS_TAB_REFRESH_RETRY_MS);
    }

    return await task();
  } finally {
    try {
      if (storage.getItem(CROSS_TAB_REFRESH_LOCK_KEY)?.startsWith(`${owner}|`)) {
        storage.removeItem(CROSS_TAB_REFRESH_LOCK_KEY);
      }
    } catch {
      // Le TTL empeche un verrou permanent si le stockage devient indisponible.
    }
  }
}

async function performTokenRefresh(): Promise<string> {
  const config = {
    withCredentials: true,
    _skipAuthRefresh: true,
  } as AxiosRequestConfig & { _skipAuthRefresh: true };

  const response = await httpClient.post<RefreshResponse>(
    REFRESH_URL,
    { client: "web" },
    config,
  );

  const token = response.data?.access;

  if (typeof token !== "string" || token.length === 0) {
    notifySessionInvalidated();
    throw new Error("Réponse de refresh invalide : access token absent");
  }

  setAccessToken(token);
  return token;
}

async function refreshAccessTokenOnce(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = withCrossTabRefreshLock(performTokenRefresh).finally(() => {
      refreshPromise = null;
    });
  }

  return refreshPromise;
}

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as AuthRequestConfig | undefined;
    const status = error.response?.status;

    if (original?._skipAuthRefresh) {
      if (
        original.url === REFRESH_URL &&
        (status === 401 || isExplicitInvalidSessionResponse(error))
      ) {
        notifySessionInvalidated();
      }

      return Promise.reject(toAppError(error));
    }

    if (isExplicitInvalidSessionResponse(error)) {
      notifySessionInvalidated();
      return Promise.reject(toAppError(error));
    }

    if (status === 401 && original && !original._retried) {
      original._retried = true;

      try {
        const newToken = await refreshAccessTokenOnce();
        original.headers.set("Authorization", `Bearer ${newToken}`);
        return httpClient(original);
      } catch (refreshError) {
        if (isTransientAppError(refreshError)) {
          return Promise.reject(refreshError);
        }
      }
    } else if (status === 401 && original?._retried) {
      notifySessionInvalidated();
    }

    return Promise.reject(toAppError(error));
  },
);
