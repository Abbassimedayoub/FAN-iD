/**
 * Client-side error taxonomy. The displayed message depends on the error
 * class, never directly on the raw HTTP status code.
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

function isAppError(error: unknown): error is AppError {
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const candidate = error as Partial<AppError>;

  return (
    typeof candidate.errorClass === "string" &&
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    typeof candidate.details === "object" &&
    candidate.details !== null &&
    (typeof candidate.httpStatus === "number" || candidate.httpStatus === null)
  );
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
 * Convert an Axios error into a typed `AppError` using the stable API error
 * envelope: `{ error: { code, message, details, correlation_id, trace_id } }`.
 */
export function toAppError(error: unknown): AppError {
  if (isAppError(error)) {
    return error;
  }

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

// Minimal utility types keep this module independent from Axios' concrete type.
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
