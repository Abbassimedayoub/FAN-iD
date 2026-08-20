import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { LoginForm } from "@/features/auth/LoginForm";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { useAuth } from "@/features/auth/AuthContext";
import type { AuthUser, UserRole } from "@/features/auth/types";
import { AdminOrganizersPage } from "@/features/organizers/AdminOrganizersPage";

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
    <main className="flex min-h-screen items-center justify-center bg-navy/5 p-6">
      <section className="flex w-full max-w-md flex-col gap-6">
        <div className="text-center">
          <h1 className="font-sora text-3xl font-bold text-navy">FAN id</h1>
          <p className="mt-2 text-sm text-navy/70">Connectez-vous à votre espace.</p>
        </div>

        <LoginForm onSuccess={onSuccess} />
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

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
