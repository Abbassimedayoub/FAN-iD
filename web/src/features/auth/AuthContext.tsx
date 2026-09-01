import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import { clearAccessToken } from "@/lib/httpClient";

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

interface AuthProviderProps {
  children: ReactNode;
  initialUser?: AuthUser | null;
}

export function AuthProvider({ children, initialUser }: AuthProviderProps) {
  const hasInitialUser = initialUser !== undefined;

  const [user, setUser] = useState<AuthUser | null>(initialUser ?? null);
  const [status, setStatus] = useState<AuthStatus>(
    hasInitialUser ? (initialUser ? "authenticated" : "anonymous") : "bootstrapping",
  );

  useEffect(() => {
    if (hasInitialUser) {
      return;
    }

    let active = true;

    void getCurrentUser()
      .then((currentUser) => {
        if (!active) {
          return;
        }

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
  }, [hasInitialUser]);

  function authenticate(authenticatedUser: AuthUser): void {
    setUser(authenticatedUser);
    setStatus("authenticated");
  }

  function clearAuthentication(): void {
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
