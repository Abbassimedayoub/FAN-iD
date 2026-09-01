import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { useAuth } from "@/features/auth/AuthContext";
import { logoutWeb } from "@/features/auth/logout";

type OrganizerNavItem =
  | "overview"
  | "events"
  | "tickets"
  | "products"
  | "orders"
  | "scanners"
  | "statistics"
  | "settings";

interface OrganizerShellProps {
  children: ReactNode;
  activeItem: OrganizerNavItem;
  breadcrumbs?: ReactNode;
}

interface IconProps {
  name: OrganizerNavItem;
}

function SidebarIcon({ name }: IconProps) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  const paths: Record<OrganizerNavItem, ReactNode> = {
    overview: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    events: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M8 3v4M16 3v4M3 10h18" />
        <path d="M8 14h3M8 17h7" />
      </>
    ),
    tickets: (
      <>
        <path d="M4 6h16v4a2.5 2.5 0 0 0 0 5v4H4v-4a2.5 2.5 0 0 0 0-5V6Z" />
        <path d="M12 8v2M12 14v2" />
      </>
    ),
    products: (
      <>
        <path d="m4 8 8-4 8 4-8 4-8-4Z" />
        <path d="m4 8v8l8 4 8-4V8" />
        <path d="M12 12v8" />
      </>
    ),
    orders: (
      <>
        <path d="M6 3h12v18H6z" />
        <path d="M9 8h6M9 12h6M9 16h4" />
      </>
    ),
    scanners: (
      <>
        <path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4" />
        <path d="M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4" />
        <path d="M7 12h10" />
      </>
    ),
    statistics: (
      <>
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1A7 7 0 0 0 15 6l-.3-2.6h-4L10.4 6A7 7 0 0 0 9 7.1l-2.4-1-2 3.4L6.6 11a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1A7 7 0 0 0 10.4 18l.3 2.6h4L15 18a7 7 0 0 0 1.5-1.1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" className="h-[19px] w-[19px]" aria-hidden="true" {...common}>
      {paths[name]}
    </svg>
  );
}

const MAIN_NAV: Array<{
  key: OrganizerNavItem;
  label: string;
  to?: string;
}> = [
  {
    key: "overview",
    label: "Vue d’ensemble",
    to: "/organizer",
  },
  {
    key: "events",
    label: "Événements",
    to: "/organizer/events",
  },
  {
    key: "tickets",
    label: "Billets",
  },
  {
    key: "products",
    label: "Produits",
  },
  {
    key: "orders",
    label: "Commandes",
  },
  {
    key: "scanners",
    label: "Scanners",
    to: "/organizer/scanners",
  },
  {
    key: "statistics",
    label: "Statistiques",
  },
];

function initials(firstName?: string, lastName?: string): string {
  return (
    [firstName, lastName]
      .filter(Boolean)
      .map((value) => value?.[0]?.toUpperCase())
      .join("")
      .slice(0, 2) || "OR"
  );
}

export function OrganizerShell({ children, activeItem, breadcrumbs }: OrganizerShellProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, clearAuthentication } = useAuth();

  const [logoutPending, setLogoutPending] = useState(false);

  const [logoutError, setLogoutError] = useState(false);

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
    <div className="min-h-screen bg-[#f5f7fb] text-navy lg:flex">
      <aside className="border-b border-white/10 bg-[#082746] text-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-[250px] lg:shrink-0 lg:flex-col lg:border-b-0 lg:border-r lg:border-white/5">
        <div className="flex min-h-[78px] items-center border-b border-white/10 px-6">
          <NavLink to="/organizer" aria-label="Accueil organisateur FANID">
            <BrandMark className="text-white" />
          </NavLink>
        </div>

        <nav
          aria-label="Navigation organisateur principale"
          className="flex gap-2 overflow-x-auto px-4 py-4 lg:flex-1 lg:flex-col lg:gap-1.5 lg:overflow-visible lg:px-4 lg:py-6"
        >
          {MAIN_NAV.map((item) => {
            const selected = item.key === activeItem;

            const className = [
              "flex min-h-[46px] shrink-0 items-center gap-3 rounded-xl px-4 text-sm font-semibold transition",
              selected
                ? "bg-[#1769d2] text-white shadow-[0_8px_24px_rgba(23,105,210,0.28)]"
                : "text-white/62 hover:bg-white/[0.07] hover:text-white",
            ].join(" ");

            if (item.to) {
              return (
                <NavLink key={item.key} to={item.to} className={className}>
                  <SidebarIcon name={item.key} />
                  <span>{item.label}</span>
                </NavLink>
              );
            }

            return (
              <button
                key={item.key}
                type="button"
                disabled
                className={`${className} cursor-not-allowed opacity-45`}
              >
                <SidebarIcon name={item.key} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="hidden border-t border-white/10 p-4 lg:block">
          <NavLink
            to="/organizer/security"
            className={[
              "flex min-h-[46px] items-center gap-3 rounded-xl px-4 text-sm font-semibold transition",
              activeItem === "settings"
                ? "bg-[#1769d2] text-white"
                : "text-white/62 hover:bg-white/[0.07] hover:text-white",
            ].join(" ")}
          >
            <SidebarIcon name="settings" />
            <span>Paramètres</span>
          </NavLink>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="flex min-h-[78px] items-center gap-4 border-b border-[#e5eaf0] bg-white px-5 sm:px-8 lg:px-10">
          <div className="min-w-0 flex-1">{breadcrumbs}</div>

          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-semibold text-[#23354d]">
                {[user?.first_name, user?.last_name].filter(Boolean).join(" ") || "Organisateur"}
              </p>
              <p className="max-w-[220px] truncate text-xs text-navy/40">{user?.email}</p>
            </div>

            <button
              type="button"
              onClick={() => {
                void handleLogout();
              }}
              disabled={logoutPending}
              title="Se déconnecter"
              aria-label={logoutPending ? "Déconnexion en cours" : "Se déconnecter"}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-[#e8f2ff] text-sm font-bold text-[#1769d2] transition hover:bg-[#dcecff] disabled:opacity-50"
            >
              {initials(user?.first_name, user?.last_name)}
            </button>
          </div>
        </header>

        {logoutError ? (
          <div
            role="alert"
            className="border-b border-red-200 bg-red-50 px-6 py-2 text-center text-sm text-red-700"
          >
            Impossible de vous déconnecter. Réessayez.
          </div>
        ) : null}

        {children}
      </div>
    </div>
  );
}
