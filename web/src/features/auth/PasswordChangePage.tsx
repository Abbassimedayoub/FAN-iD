import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button, Card, Input } from "@/components/primitives";

import { useAuth } from "./AuthContext";
import { changePassword } from "./passwordChange";

interface FieldErrors {
  currentPassword?: string;
  newPassword?: string;
  confirmPassword?: string;
}

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}

function firstMessage(value: unknown): string | null {
  if (typeof value === "string" && value.length > 0) {
    return value;
  }

  if (Array.isArray(value)) {
    const first = value.find((item): item is string => typeof item === "string" && item.length > 0);
    return first ?? null;
  }

  return null;
}

function fieldMessage(error: unknown, field: string): string | null {
  if (!isRecord(error) || !isRecord(error["details"])) {
    return null;
  }

  return firstMessage(error["details"][field]);
}

function errorStatus(error: unknown): number | null {
  if (!isRecord(error)) {
    return null;
  }

  return typeof error["status"] === "number" ? error["status"] : null;
}

function genericErrorMessage(error: unknown): string {
  if (errorStatus(error) === 429) {
    return "Trop de tentatives. Réessayez un peu plus tard.";
  }

  return "Impossible de modifier le mot de passe. Réessayez.";
}

function Rule({
  valid,
  children,
  serverOnly = false,
}: {
  valid?: boolean;
  children: string;
  serverOnly?: boolean;
}) {
  const active = valid === true;

  return (
    <li className={`flex gap-2 ${active ? "text-emerald-700" : "text-navy/55"}`}>
      <span aria-hidden="true">{active ? "✓" : serverOnly ? "◆" : "○"}</span>
      <span>{children}</span>
    </li>
  );
}

export function PasswordChangePage() {
  const navigate = useNavigate();
  const { clearAuthentication, user } = useAuth();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const hasMinimumLength = newPassword.length >= 10;
  const isNotOnlyNumeric = newPassword.length > 0 && !/^\d+$/.test(newPassword);
  const confirmationMatches = confirmPassword.length > 0 && newPassword === confirmPassword;

  const isOrganizer = user?.role === "ORGANIZER";
  const accountLabel = isOrganizer ? "Compte organisateur" : "Compte administrateur";
  const backTarget = isOrganizer ? "/organizer" : "/admin/organizers";
  const roleLabel = isOrganizer ? "Organisateur" : "Administrateur";

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    setFieldErrors({});
    setFormError(null);

    if (newPassword !== confirmPassword) {
      setFieldErrors({
        confirmPassword: "Les deux nouveaux mots de passe ne correspondent pas.",
      });
      return;
    }

    setSubmitting(true);

    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      clearAuthentication();
      navigate("/login?passwordChanged=1", { replace: true });
    } catch (error) {
      if (errorStatus(error) === 401) {
        clearAuthentication();
        navigate("/login", { replace: true });
        return;
      }

      const currentPasswordError = fieldMessage(error, "current_password");
      const newPasswordError = fieldMessage(error, "new_password");

      setFieldErrors({
        currentPassword: currentPasswordError ?? undefined,
        newPassword: newPasswordError ?? undefined,
      });

      if (!currentPasswordError && !newPasswordError) {
        setFormError(genericErrorMessage(error));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1200px] px-5 py-8 sm:px-8 sm:py-10">
      <div className="mb-8">
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">
          {accountLabel}
        </p>

        <h1 className="font-sora text-3xl font-bold tracking-[-0.03em] text-navy">Sécurité</h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-navy/55">
          Gérez les accès sensibles associés à votre compte FANID.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="p-6 sm:p-8">
          <div className="mb-7">
            <h2 className="font-sora text-xl font-bold text-navy">Changer le mot de passe</h2>

            <p className="mt-2 text-sm leading-6 text-navy/55">
              Pour votre sécurité, votre mot de passe actuel est nécessaire.
            </p>
          </div>

          <form className="space-y-5" onSubmit={onSubmit}>
            <div>
              <label
                htmlFor="current-password"
                className="mb-2 block text-sm font-semibold text-navy"
              >
                Mot de passe actuel
              </label>

              <Input
                id="current-password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={128}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                aria-invalid={Boolean(fieldErrors.currentPassword)}
                aria-describedby={
                  fieldErrors.currentPassword ? "current-password-error" : undefined
                }
                className="w-full"
              />

              {fieldErrors.currentPassword ? (
                <p id="current-password-error" role="alert" className="mt-2 text-sm text-red-700">
                  {fieldErrors.currentPassword}
                </p>
              ) : null}
            </div>

            <div>
              <label htmlFor="new-password" className="mb-2 block text-sm font-semibold text-navy">
                Nouveau mot de passe
              </label>

              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                required
                maxLength={128}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                aria-invalid={Boolean(fieldErrors.newPassword)}
                aria-describedby="password-rules"
                className="w-full"
              />

              {fieldErrors.newPassword ? (
                <p id="new-password-error" role="alert" className="mt-2 text-sm text-red-700">
                  {fieldErrors.newPassword}
                </p>
              ) : null}

              <div
                id="password-rules"
                className="mt-4 rounded-2xl border border-[#e2e9f0] bg-[#f8fafc] p-4"
              >
                <p className="text-xs font-bold uppercase tracking-[0.12em] text-navy/55">
                  Conditions du mot de passe
                </p>

                <ul className="mt-3 space-y-2 text-sm">
                  <Rule valid={hasMinimumLength}>Contenir au moins 10 caractères.</Rule>

                  <Rule valid={isNotOnlyNumeric}>Ne pas être entièrement numérique.</Rule>

                  <Rule serverOnly>
                    Ne pas être trop similaire à votre adresse e-mail, votre nom ou vos informations
                    personnelles.
                  </Rule>

                  <Rule serverOnly>Ne pas être un mot de passe couramment utilisé.</Rule>
                </ul>

                <p className="mt-4 text-xs leading-5 text-navy/40">
                  ◆ Vérifié exactement par Django au moment de la modification.
                </p>
              </div>
            </div>

            <div>
              <label
                htmlFor="confirm-password"
                className="mb-2 block text-sm font-semibold text-navy"
              >
                Confirmer le nouveau mot de passe
              </label>

              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                required
                maxLength={128}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                aria-invalid={Boolean(fieldErrors.confirmPassword)}
                aria-describedby={
                  fieldErrors.confirmPassword ? "confirm-password-error" : undefined
                }
                className="w-full"
              />

              {fieldErrors.confirmPassword ? (
                <p id="confirm-password-error" role="alert" className="mt-2 text-sm text-red-700">
                  {fieldErrors.confirmPassword}
                </p>
              ) : null}

              {confirmPassword.length > 0 && !fieldErrors.confirmPassword ? (
                <p
                  className={`mt-2 text-xs font-semibold ${
                    confirmationMatches ? "text-emerald-700" : "text-amber-700"
                  }`}
                >
                  {confirmationMatches
                    ? "✓ Les deux nouveaux mots de passe correspondent."
                    : "○ Les deux nouveaux mots de passe ne correspondent pas encore."}
                </p>
              ) : null}
            </div>

            {formError ? (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
              >
                {formError}
              </div>
            ) : null}

            <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
              <Link
                to={backTarget}
                className="inline-flex min-h-[44px] items-center justify-center rounded-xl px-4 py-2 text-sm font-semibold text-navy/60 transition hover:bg-navy/5 hover:text-navy"
              >
                Annuler
              </Link>

              <Button type="submit" disabled={submitting} className="sm:min-w-[210px]">
                {submitting ? "Modification…" : "Changer le mot de passe"}
              </Button>
            </div>
          </form>
        </Card>

        <div className="space-y-5">
          <Card className="p-6">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-cyan/10 text-xl">
              🔒
            </div>

            <h2 className="font-sora text-lg font-bold text-navy">Déconnexion automatique</h2>

            <p className="mt-3 text-sm leading-6 text-navy/55">
              Après la modification, toutes les sessions ouvertes seront fermées, y compris celle de
              ce navigateur.
            </p>
          </Card>

          <Card className="p-6">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-navy/40">
              Compte connecté
            </p>

            <p className="mt-3 break-all text-sm font-semibold text-navy">{user?.email}</p>

            <p className="mt-1 text-xs text-navy/45">Rôle : {roleLabel}</p>
          </Card>
        </div>
      </div>
    </main>
  );
}
