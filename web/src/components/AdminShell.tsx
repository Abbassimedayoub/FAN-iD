import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Badge } from "@/components/primitives";
import { useAuth } from "@/features/auth/AuthContext";
import { logoutWeb } from "@/features/auth/logout";

type AdminNavKey = "home" | "organizers" | "security" | "sessions";

const NAVIGATION: Array<{ key: AdminNavKey; label: string; to: string }> = [
  { key: "home", label: "Accueil", to: "/admin" },
  { key: "organizers", label: "Organisateurs", to: "/admin/organizers" },
  { key: "security", label: "Sécurité", to: "/admin/security" },
  { key: "sessions", label: "Sessions", to: "/sessions" },
];

function NavIcon({ item }: { item: AdminNavKey }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  const icon: Record<AdminNavKey, ReactNode> = {
    home: <path d="m3 10 9-7 9 7v11H3V10Z" />,
    organizers: (
      <>
        <circle cx="9" cy="8" r="3.5" />
        <path d="M2.5 20c0-3.4 2.9-5.5 6.5-5.5s6.5 2.1 6.5 5.5M16.5 5.2a3.5 3.5 0 0 1 0 6.6M17 20c0-2.2-.7-3.9-1.9-5" />
      </>
    ),
    security: (
      <>
        <path d="m12 3 7 3v6c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3Z" />
        <path d="m9 12 2 2 4-4" />
      </>
    ),
    sessions: (
      <>
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M8 20h8M12 16v4" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" aria-hidden="true" {...common}>
      {icon[item]}
    </svg>
  );
}

function pageTitle(pathname: string): string {
  if (pathname.startsWith("/admin/organizers")) return "Organisateurs";
  if (pathname.startsWith("/admin/security")) return "Sécurité";
  if (pathname.startsWith("/sessions")) return "Sessions";
  return "Accueil";
}

function initials(firstName?: string, lastName?: string): string {
  return (
    [firstName, lastName]
      .filter(Boolean)
      .map((value) => value?.[0]?.toUpperCase())
      .join("")
      .slice(0, 2) || "AD"
  );
}

function desktopNavClass({ isActive }: { isActive: boolean }): string {
  return [
    "flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm transition",
    isActive
      ? "bg-primary text-white font-bold shadow-[0_5px_14px_rgba(22,99,199,0.25)]"
      : "font-medium text-[#b9c9dd] hover:bg-white/10 hover:text-white",
  ].join(" ");
}

function mobileNavClass({ isActive }: { isActive: boolean }): string {
  return [
    "whitespace-nowrap rounded-lg px-3 py-2 text-sm transition",
    isActive
      ? "bg-primary/10 font-bold text-primary"
      : "font-semibold text-navy/60 hover:bg-navy/5",
  ].join(" ");
}

export function AdminShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { user, clearAuthentication } = useAuth();

  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState(false);

  const fullName = [user?.first_name, user?.last_name].filter(Boolean).join(" ");
  const accountLabel = fullName || "Compte administrateur";
  const currentTitle = pageTitle(location.pathname);

  async function handleLogout(): Promise<void> {
    setLogoutPending(true);
    setLogoutError(false);

    try {
      await logoutWeb();
      await queryClient.cancelQueries();

      navigate("/login", { replace: true, flushSync: true });

      clearAuthentication();
      queryClient.clear();
    } catch {
      setLogoutError(true);
      setLogoutPending(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f4f7fb] lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="hidden min-h-screen flex-col bg-[linear-gradient(160deg,#0b2545,#143a63)] px-3 py-6 lg:flex">
        <NavLink to="/admin" aria-label="Accueil administrateur FANID" className="px-3">
          <BrandMark compact className="text-white" />
        </NavLink>

        <p className="mt-8 px-3 text-[10px] font-bold uppercase tracking-[0.09em] text-[#6b8cb4]">
          Administration
        </p>

        <nav aria-label="Navigation administrateur" className="mt-3 flex flex-col gap-1">
          {NAVIGATION.map((item) => (
            <NavLink
              key={item.key}
              to={item.to}
              end={item.to === "/admin"}
              className={desktopNavClass}
            >
              <NavIcon item={item.key} />
              {item.label}{" "}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto border-t border-white/10 px-3 pt-5">
          <div className="flex items-center gap-3">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-cyan/15 text-xs font-bold text-cyan">
              {initials(user?.first_name, user?.last_name)}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-white">Compte administrateur</p>
              <p className="truncate text-xs text-[#8fb0d4]">Espace sécurisé FAN-iD</p>
            </div>
          </div>
          <div className="mt-4">
            <Badge tone="info">Admin</Badge>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-40 border-b border-[#e3eaf3] bg-white/95 backdrop-blur">
          <div className="flex min-h-[68px] items-center gap-3 px-5 sm:px-8">
            <NavLink to="/admin" aria-label="Accueil administrateur FANID" className="lg:hidden">
              <BrandMark compact className="text-navy" />
            </NavLink>

            <div>
              <p className="text-sm font-bold text-navy">{currentTitle}</p>
              <p className="hidden text-xs text-[#5b6472] sm:block">Espace administrateur FAN-iD</p>
            </div>

            <div className="ml-auto flex items-center gap-3">
              <div className="hidden text-right xl:block">
                <p className="text-sm font-bold text-navy">{accountLabel}</p>
                <p className="max-w-[230px] truncate text-xs text-[#5b6472]">{user?.email}</p>
              </div>

              <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-[#eef4fc] text-xs font-bold text-primary lg:hidden">
                {initials(user?.first_name, user?.last_name)}
              </span>

              <button
                type="button"
                onClick={() => {
                  void handleLogout();
                }}
                disabled={logoutPending}
                aria-label={logoutPending ? "Déconnexion en cours" : "Se déconnecter"}
                className="inline-flex min-h-10 items-center justify-center rounded-xl border border-red-200 bg-red-50 px-3 text-sm font-bold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50 sm:px-4"
              >
                {logoutPending ? "Déconnexion…" : "Se déconnecter"}
              </button>
            </div>
          </div>

          <nav
            aria-label="Navigation administrateur mobile"
            className="flex gap-1 overflow-x-auto border-t border-[#edf2f8] px-4 py-2 lg:hidden"
          >
            {NAVIGATION.map((item) => (
              <NavLink
                key={item.key}
                to={item.to}
                end={item.to === "/admin"}
                className={mobileNavClass}
              >
                {item.label}
              </NavLink>
            ))}
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
    </div>
  );
}
