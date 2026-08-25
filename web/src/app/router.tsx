import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { LoginForm } from "@/features/auth/LoginForm";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { useAuth } from "@/features/auth/AuthContext";
import { USER_ROLES, type AuthUser, type UserRole } from "@/features/auth/types";
import { AdminOrganizerDetailPage } from "@/features/organizers/AdminOrganizerDetailPage";
import { AdminOrganizersPage } from "@/features/organizers/AdminOrganizersPage";
import { SessionsPage } from "@/features/sessions/SessionsPage";

const HOME_BY_ROLE: Record<UserRole, string> = {
  ADMIN: "/admin/organizers",
  ORGANIZER: "/organizer",
  FAN: "/forbidden",
  SCANNER: "/forbidden",
};

function LoginPage() {
  const { authenticate } = useAuth();
  const navigate = useNavigate();

  function onSuccess(user: AuthUser): void {
    authenticate(user);
    navigate(HOME_BY_ROLE[user.role], { replace: true });
  }

  return (
    <main className="min-h-screen bg-[#eef4f9] p-4 sm:p-6 lg:p-8">
      <section className="mx-auto grid min-h-[calc(100vh-2rem)] w-full max-w-[1500px] overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_30px_90px_rgba(14,42,77,0.12)] sm:min-h-[calc(100vh-3rem)] lg:grid-cols-[0.92fr_1.08fr]">
        <aside className="relative hidden overflow-hidden bg-[#0b3157] px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-14 xl:py-14">
          <div
            className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full border border-cyan/10"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -left-10 -top-10 h-48 w-48 rounded-full border border-cyan/10"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -bottom-40 right-[-100px] h-[420px] w-[420px] rounded-full border border-cyan/10"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -bottom-24 right-[-30px] h-[270px] w-[270px] rounded-full border border-cyan/10"
            aria-hidden="true"
          />

          <BrandMark className="relative z-10 text-white" />

          <div className="relative z-10 max-w-xl pb-10">
            <BrandMark compact className="mb-8" />

            <h1 className="font-sora text-4xl font-bold leading-[1.12] tracking-[-0.03em] xl:text-5xl">
              Pilotez vos
              <br />
              événements.
              <br />
              Éliminez la fraude.
            </h1>

            <p className="mt-7 max-w-md text-sm leading-7 text-white/60">
              Billetterie sécurisée par QR dynamique, contrôle d’accès en temps réel et ventes
              centralisées.
            </p>
          </div>

          <p className="relative z-10 text-xs text-white/35">FANID · Secure ticketing platform</p>
        </aside>

        <div className="relative flex items-center justify-center px-5 py-12 sm:px-10 lg:px-14 xl:px-20">
          <div
            className="pointer-events-none absolute right-[-120px] top-[-120px] h-80 w-80 rounded-full bg-cyan/5 blur-3xl"
            aria-hidden="true"
          />

          <div className="relative z-10 w-full max-w-[430px]">
            <div className="mb-9 lg:hidden">
              <BrandMark className="text-navy" />
            </div>

            <div className="mb-7">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">
                Espace organisateur
              </p>

              <h2 className="font-sora text-3xl font-bold tracking-[-0.03em] text-navy">
                Bon retour.
              </h2>

              <p className="mt-3 text-sm leading-6 text-navy/55">
                Connectez-vous pour gérer vos événements.
              </p>
            </div>

            <LoginForm onSuccess={onSuccess} />

            <div className="mt-5 flex items-start gap-3 rounded-2xl border border-cyan/20 bg-cyan/5 px-4 py-3">
              <span
                className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-cyan/15 text-xs"
                aria-hidden="true"
              >
                🔒
              </span>

              <p className="text-xs leading-5 text-navy/55">
                Votre compte est protégé par les contrôles de sécurité FANID.
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function ForbiddenPage() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6 text-center">
      <div>
        <h1 className="font-sora text-2xl font-bold text-navy">Accès refusé</h1>
        <p className="mt-2 text-navy/70">Votre rôle ne permet pas d’accéder à cet espace.</p>
      </div>
    </main>
  );
}

function OrganizerHomePage() {
  return (
    <main className="p-8">
      <h1 className="font-sora text-2xl font-bold text-navy">Espace organisateur</h1>
    </main>
  );
}

function HomeRedirect() {
  const { user } = useAuth();

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={HOME_BY_ROLE[user.role]} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forbidden" element={<ForbiddenPage />} />

      <Route
        path="/sessions"
        element={
          <ProtectedRoute allowedRoles={USER_ROLES}>
            <SessionsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/organizer"
        element={
          <ProtectedRoute allowedRoles={["ORGANIZER"]}>
            <OrganizerHomePage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/organizers"
        element={
          <ProtectedRoute allowedRoles={["ADMIN"]}>
            <AdminOrganizersPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/organizers/:organizerId"
        element={
          <ProtectedRoute allowedRoles={["ADMIN"]}>
            <AdminOrganizerDetailPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
