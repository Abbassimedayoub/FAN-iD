import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Badge } from "@/components/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { logoutWeb } from "@/features/auth/logout";

function navClass({ isActive }: { isActive: boolean }): string {
  return [
    "rounded-xl px-3 py-2 text-sm font-semibold transition",
    isActive ? "bg-primary/10 text-primary" : "text-navy/55 hover:bg-navy/5 hover:text-navy",
  ].join(" ");
}

export function AdminShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, clearAuthentication } = useAuth();

  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState(false);

  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ");
  const accountLabel = fullName || "Compte administrateur";

  async function handleLogout(): Promise<void> {
    setLogoutPending(true);
    setLogoutError(false);

    try {
      await logoutWeb();
      await queryClient.cancelQueries();

      navigate("/login", {
        replace: true,
        flushSync: true,
      });

      clearAuthentication();
      queryClient.clear();
    } catch {
      setLogoutError(true);
      setLogoutPending(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f4f7fb]">
      <header className="sticky top-0 z-40 border-b border-[#e3eaf1] bg-white/95 backdrop-blur">
        <div className="mx-auto flex min-h-[72px] max-w-[1500px] items-center gap-5 px-5 sm:px-8">
          <NavLink
            to="/admin/organizers"
            aria-label="Accueil administrateur FANID"
            className="shrink-0"
          >
            <BrandMark compact className="text-navy" />
          </NavLink>

          <nav aria-label="Navigation administrateur" className="hidden items-center gap-1 md:flex">
            <NavLink to="/admin/organizers" className={navClass}>
              Organisateurs
            </NavLink>

            <NavLink to="/admin/security" className={navClass}>
              Sécurité
            </NavLink>

            <NavLink to="/sessions" className={navClass}>
              Sessions
            </NavLink>
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right lg:block">
              <p className="text-sm font-semibold text-navy">{accountLabel}</p>
              <p className="max-w-[220px] truncate text-xs text-navy/45">{user?.email}</p>
            </div>

            {user?.role ? <Badge>{user.role === "ADMIN" ? "Admin" : user.role}</Badge> : null}

            <button
              type="button"
              onClick={() => {
                void handleLogout();
              }}
              disabled={logoutPending}
              aria-label={logoutPending ? "Déconnexion en cours" : "Se déconnecter"}
              className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100 focus:outline-none focus:ring-4 focus:ring-red-100 disabled:cursor-not-allowed disabled:opacity-50 sm:px-4"
            >
              <span className="sm:hidden" aria-hidden="true">
                ↪
              </span>
              <span className="hidden sm:inline" aria-hidden="true">
                {logoutPending ? "Déconnexion…" : "Se déconnecter"}
              </span>
            </button>
          </div>
        </div>

        <nav
          aria-label="Navigation administrateur mobile"
          className="flex gap-1 overflow-x-auto border-t border-[#eef2f6] px-4 py-2 md:hidden"
        >
          <NavLink to="/admin/organizers" className={navClass}>
            Organisateurs
          </NavLink>

          <NavLink to="/admin/security" className={navClass}>
            Sécurité
          </NavLink>

          <NavLink to="/sessions" className={navClass}>
            Sessions
          </NavLink>
        </nav>

        {logoutError ? (
          <div
            role="alert"
            className="border-t border-red-200 bg-red-50 px-5 py-2 text-center text-sm text-red-800"
          >
            Impossible de vous déconnecter. Réessayez.
          </div>
        ) : null}
      </header>

      {children}
    </div>
  );
}
