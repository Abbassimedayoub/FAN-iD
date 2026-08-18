/**
 * Taxonomie des erreurs côté client (§4.2 Source B) — le message affiché
 * dépend de la CLASSE d'erreur, jamais du code HTTP brut affiché tel quel.
 */
export type AppErrorClass =
  "network" | "auth" | "permission" | "not_found" | "business" | "server" | "unknown";

export interface AppError {
  errorClass: AppErrorClass;
  code: string;
  message: string;
  details: Record<string, unknown>;
  correlationId: string | null;
  traceId: string | null;
  httpStatus: number | null;
}

interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    correlation_id?: string;
    trace_id?: string;
  };
}

function isApiErrorBody(data: unknown): data is ApiErrorBody {
  return (
    typeof data === "object" &&
    data !== null &&
    "error" in data &&
    typeof (data as { error?: unknown }).error === "object"
  );
}

/**
 * Traduit une erreur Axios en `AppError` typée, selon le contrat d'erreur
 * gelé au Sprint 0 (`{ error: { code, message, details, correlation_id,
 * trace_id } }`, §17 master prompt / §3.3 Source B).
 */
export function toAppError(error: unknown): AppError {
  const httpStatus = getHttpStatus(error);
  const data = getResponseData(error);

  if (httpStatus === null) {
    return {
      errorClass: "network",
      code: "NETWORK_ERROR",
      message: "Connexion indisponible",
      details: {},
      correlationId: null,
      traceId: null,
      httpStatus: null,
    };
  }

  const body: ApiErrorBody["error"] | null = isApiErrorBody(data) ? data.error : null;
  const code = body?.code ?? "UNKNOWN_ERROR";
  const message = body?.message ?? "Un problème est survenu de notre côté";

  return {
    errorClass: classify(httpStatus, code),
    code,
    message,
    details: body?.details ?? {},
    correlationId: body?.correlation_id ?? null,
    traceId: body?.trace_id ?? null,
    httpStatus,
  };
}

function classify(httpStatus: number, _code: string): AppErrorClass {
  if (httpStatus === 401) return "auth";
  if (httpStatus === 403) return "permission";
  if (httpStatus === 404) return "not_found";
  if ([400, 409, 422].includes(httpStatus)) return "business";
  if (httpStatus >= 500) return "server";
  return "unknown";
}

// Types utilitaires minimaux pour ne pas dépendre directement du type Axios ici.
interface MaybeAxiosError {
  response?: { status?: number; data?: unknown };
}

function getHttpStatus(error: unknown): number | null {
  const maybe = error as MaybeAxiosError;
  return maybe?.response?.status ?? null;
}

function getResponseData(error: unknown): unknown {
  const maybe = error as MaybeAxiosError;
  return maybe?.response?.data ?? null;
}
