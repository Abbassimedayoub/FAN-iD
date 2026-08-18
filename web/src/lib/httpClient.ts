/**
 * Client Axios (§46 master prompt / §4.3 Source B) : injection du Bearer,
 * génération de `X-Correlation-ID`, refresh UNIQUE mis en file (évite le
 * bug classique : N requêtes 401 parallèles déclenchant N refresh, dont
 * N-1 échouent à cause de la rotation et déconnectent l'utilisateur
 * aléatoirement), mapping vers `AppError` typée.
 *
 * Le CONTENU métier du refresh (endpoint, rotation, détection de réutilisation)
 * est spécifié et implémenté au Sprint 1 — ce module ne fournit que le
 * mécanisme de verrouillage générique, avec un point d'extension explicite.
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { toAppError } from "./errors";

const CORRELATION_HEADER = "X-Correlation-ID";

function generateCorrelationId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export const httpClient = axios.create({
  baseURL: import.meta.env["VITE_API_URL"] ?? "http://localhost:8000",
  timeout: 10_000,
});

httpClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  config.headers.set(CORRELATION_HEADER, generateCorrelationId());

  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

// --- Verrou de refresh : une seule requête de refresh à la fois ---
let refreshPromise: Promise<string> | null = null;

/**
 * Point d'extension Sprint 1 : la vraie logique d'appel réseau au endpoint
 * de refresh (rotation + détection de réutilisation, ADR Source A §Sprint1)
 * sera injectée ici. Le Sprint 0 fournit le VERROU, pas l'appel réseau.
 */
async function performTokenRefresh(): Promise<string> {
  throw new Error(
    "performTokenRefresh() n'est pas implémenté au Sprint 0 — logique de " +
      "rotation de refresh token livrée au Sprint 1 (identity).",
  );
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
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      try {
        const newToken = await refreshAccessTokenOnce();
        original.headers.set("Authorization", `Bearer ${newToken}`);
        return httpClient(original);
      } catch {
        // Refresh impossible : redirection silencieuse vers la connexion
        // (comportement défini au Sprint 1, taxonomie §4.2 Source B).
      }
    }

    return Promise.reject(toAppError(error));
  },
);

// --- Stockage du token — coquille Sprint 0 (implémentation sécurisée Sprint 1) ---
function getAccessToken(): string | null {
  return null;
}
