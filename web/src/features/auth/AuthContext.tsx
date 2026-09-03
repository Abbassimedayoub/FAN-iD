import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import {
  AUTH_SESSION_INVALIDATED_EVENT,
  clearAccessToken,
  getAccessToken,
} from "@/lib/httpClient";

import { logoutWeb } from "./logout";
import {
  BROWSER_ACTIVITY_STORAGE_KEY,
  BROWSER_SESSION_BLOCKED_STORAGE_KEY,
  WEB_INACTIVITY_TIMEOUT_MS,
  browserSessionHasTimedOut,
  clearBrowserSessionBlock,
  isBrowserSessionBlocked,
  markBrowserSessionBlocked,
  readBrowserActivity,
  recordBrowserActivity,
} from "./sessionActivity";
import { getCurrentUser } from "./session";
import type { AuthUser } from "./types";

export type AuthStatus = "bootstrapping" | "authenticated" | "anonymous";

interface AuthContextValue {
  user: AuthUser | null;
  status: AuthStatus;
  authenticate: (user: AuthUser) => void;
  clearAuthentication: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const SESSION_VALIDATION_INTERVAL_MS = 30_000;
const ACTIVITY_EVENTS: readonly (keyof WindowEventMap)[] = [
  "pointerdown",
  "keydown",
  "touchstart",
  "wheel",
];

interface AuthProviderProps {
  children: ReactNode;
  initialUser?: AuthUser | null;
  inactivityTimeoutMs?: number;
}

function isTransientValidationFailure(error: unknown): boolean {
  if (typeof error !== "object" || error === null || !("errorClass" in error)) {
    return false;
  }

  const errorClass = (error as { errorClass?: unknown }).errorClass;
  return errorClass === "network" || errorClass === "server";
}

export function AuthProvider({
  children,
  initialUser,
  inactivityTimeoutMs = WEB_INACTIVITY_TIMEOUT_MS,
}: AuthProviderProps) {
  const hasInitialUser = initialUser !== undefined;

  const [user, setUser] = useState<AuthUser | null>(initialUser ?? null);
  const [status, setStatus] = useState<AuthStatus>(
    hasInitialUser ? (initialUser ? "authenticated" : "anonymous") : "bootstrapping",
  );

  useEffect(() => {
    const handleSessionInvalidated = (): void => {
      markBrowserSessionBlocked();
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
    };

    window.addEventListener(AUTH_SESSION_INVALIDATED_EVENT, handleSessionInvalidated);

    return () => {
      window.removeEventListener(AUTH_SESSION_INVALIDATED_EVENT, handleSessionInvalidated);
    };
  }, []);

  useEffect(() => {
    if (hasInitialUser) {
      return;
    }

    if (
      isBrowserSessionBlocked() ||
      browserSessionHasTimedOut(inactivityTimeoutMs)
    ) {
      markBrowserSessionBlocked();
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");
      return;
    }

    let active = true;

    void getCurrentUser()
      .then((currentUser) => {
        if (!active) {
          return;
        }

        if (isBrowserSessionBlocked()) {
          clearAccessToken();
          setUser(null);
          setStatus("anonymous");
          return;
        }

        recordBrowserActivity();
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!active) {
          return;
        }

        clearAccessToken();
        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      active = false;
    };
  }, [hasInitialUser, inactivityTimeoutMs]);

  useEffect(() => {
    if (hasInitialUser || status !== "authenticated") {
      return;
    }

    let active = true;

    const validateSession = async (): Promise<void> => {
      try {
        const currentUser = await getCurrentUser();

        if (active && !isBrowserSessionBlocked()) {
          setUser(currentUser);
        }
      } catch (error) {
        if (!active || isTransientValidationFailure(error)) {
          return;
        }

        markBrowserSessionBlocked();
        clearAccessToken();
        setUser(null);
        setStatus("anonymous");
      }
    };

    const handleFocus = (): void => {
      void validateSession();
    };

    const handleVisibilityChange = (): void => {
      if (document.visibilityState === "visible") {
        void validateSession();
      }
    };

    const intervalId = window.setInterval(
      () => {
        void validateSession();
      },
      SESSION_VALIDATION_INTERVAL_MS,
    );

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      active = false;
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [hasInitialUser, status]);

  useEffect(() => {
    if (status !== "authenticated") {
      return;
    }

    let timeoutId: number | null = null;
    let expiring = false;

    const expireForInactivity = (): void => {
      if (expiring) {
        return;
      }

      expiring = true;

      const bearer = getAccessToken();

      markBrowserSessionBlocked();
      clearAccessToken();
      setUser(null);
      setStatus("anonymous");

      void logoutWeb(bearer ?? undefined)
        .catch(() => undefined)
        .finally(() => {
          clearAccessToken();
        });
    };

    const scheduleTimeout = (): void => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }

      let lastActivity = readBrowserActivity();

      if (lastActivity === null) {
        lastActivity = Date.now();
        recordBrowserActivity(lastActivity);
      }

      const elapsed = Math.max(0, Date.now() - lastActivity);
      const remaining = Math.max(0, inactivityTimeoutMs - elapsed);

      timeoutId = window.setTimeout(() => {
        if (browserSessionHasTimedOut(inactivityTimeoutMs)) {
          expireForInactivity();
          return;
        }

        scheduleTimeout();
      }, remaining);
    };

    const handleActivity = (): void => {
      if (browserSessionHasTimedOut(inactivityTimeoutMs)) {
        expireForInactivity();
        return;
      }

      recordBrowserActivity();
      scheduleTimeout();
    };

    const handleVisibilityChange = (): void => {
      if (document.visibilityState === "visible") {
        handleActivity();
      }
    };

    const handleStorage = (event: StorageEvent): void => {
      if (
        event.key === BROWSER_SESSION_BLOCKED_STORAGE_KEY &&
        event.newValue === "1"
      ) {
        clearAccessToken();
        setUser(null);
        setStatus("anonymous");
        return;
      }

      if (event.key === BROWSER_ACTIVITY_STORAGE_KEY) {
        scheduleTimeout();
      }
    };

    scheduleTimeout();

    for (const eventName of ACTIVITY_EVENTS) {
      window.addEventListener(eventName, handleActivity, { passive: true });
    }

    window.addEventListener("focus", handleActivity);
    window.addEventListener("storage", handleStorage);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }

      for (const eventName of ACTIVITY_EVENTS) {
        window.removeEventListener(eventName, handleActivity);
      }

      window.removeEventListener("focus", handleActivity);
      window.removeEventListener("storage", handleStorage);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [inactivityTimeoutMs, status]);

  function authenticate(authenticatedUser: AuthUser): void {
    clearBrowserSessionBlock();
    recordBrowserActivity();
    setUser(authenticatedUser);
    setStatus("authenticated");
  }

  function clearAuthentication(): void {
    markBrowserSessionBlocked();
    clearAccessToken();
    setUser(null);
    setStatus("anonymous");
  }

  if (status === "bootstrapping") {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <p role="status" className="text-sm text-navy/70">
          Restauration de la session…
        </p>
      </main>
    );
  }

  return (
    <AuthContext.Provider value={{ user, status, authenticate, clearAuthentication }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth doit être utilisé dans AuthProvider.");
  }

  return context;
}
