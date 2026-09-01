import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { Button, Card, Input } from "@/components/primitives";

import { PublicRecoveryShell } from "./PublicRecoveryShell";
import { confirmPasswordReset } from "./passwordReset";

interface PasswordFieldProps {
  id: string;
  label: string;
  value: string;
  confirmation?: boolean;
  onChange: (value: string) => void;
}

function PasswordField({ id, label, value, confirmation = false, onChange }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-[13px] font-semibold text-navy">
        {label}
      </label>

      <div className="relative">
        <Input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete={confirmation ? "new-password" : "new-password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="min-h-[50px] w-full pr-14"
          placeholder="••••••••••••"
        />

        <button
          type="button"
          onClick={() => setVisible((current) => !current)}
          aria-label={
            visible ? `Masquer ${label.toLowerCase()}` : `Afficher ${label.toLowerCase()}`
          }
          aria-pressed={visible}
          className="absolute right-1 top-1/2 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-lg text-navy/60 transition hover:bg-navy/5 hover:text-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          {visible ? (
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <path d="m3 3 18 18" />
              <path d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
              <path d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.5 0 9.5 5 9.5 5a16.3 16.3 0 0 1-3 3.5" />
              <path d="M6.6 6.6C4 8.3 2.5 11 2.5 11s4 5 9.5 5a10.6 10.6 0 0 0 4-.8" />
            </svg>
          ) : (
            <svg
              aria-hidden="true"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
            >
              <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}

function fieldPasswordMessage(error: unknown): string | null {
  if (typeof error !== "object" || error === null || !("details" in error)) {
    return null;
  }

  const details = (error as { details?: unknown }).details;

  if (typeof details !== "object" || details === null) {
    return null;
  }

  const value = (details as Record<string, unknown>)["new_password"];

  if (Array.isArray(value)) {
    const first = value.find((item) => typeof item === "string");
    return typeof first === "string" ? first : null;
  }

  return typeof value === "string" ? value : null;
}

function resetErrorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (error as { code?: unknown }).code;

    if (code === "PASSWORD_RESET_INVALID") {
      return "Le lien ou le code est invalide ou a expiré. Demandez un nouvel e-mail.";
    }

    if (code === "OTP_MAX_ATTEMPTS") {
      return "Trop de codes incorrects ont été saisis. Demandez un nouveau code.";
    }

    if (code === "RATE_LIMIT_EXCEEDED") {
      return "Trop de tentatives. Réessayez un peu plus tard.";
    }

    if (code === "PASSWORD_UNCHANGED") {
      return "Choisissez un mot de passe différent de l’ancien.";
    }

    const passwordMessage = fieldPasswordMessage(error);

    if (passwordMessage) {
      return passwordMessage;
    }

    if (code === "VALIDATION_ERROR") {
      return "Vérifiez le nouveau mot de passe.";
    }
  }

  return "Impossible de réinitialiser le mot de passe. Réessayez.";
}

export function PasswordResetPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const token = searchParams.get("token")?.trim() ?? "";
  const locationState = location.state as { email?: string } | null;

  const [email, setEmail] = useState(locationState?.email ?? "");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const magicMode = token.length > 0;

  const hasMinimumLength = newPassword.length >= 10;
  const notOnlyNumeric = newPassword.length > 0 && !/^\d+$/.test(newPassword);
  const passwordsMatch = confirmation.length > 0 && confirmation === newPassword;

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);

    if (!newPassword) {
      setError("Saisissez votre nouveau mot de passe.");
      return;
    }

    if (newPassword !== confirmation) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }

    if (!magicMode) {
      if (!email.trim()) {
        setError("Adresse e-mail requise.");
        return;
      }

      if (!/^\d{6}$/.test(code)) {
        setError("Le code doit contenir exactement 6 chiffres.");
        return;
      }
    }

    setLoading(true);

    try {
      if (magicMode) {
        await confirmPasswordReset({
          token,
          new_password: newPassword,
        });
      } else {
        await confirmPasswordReset({
          email: email.trim(),
          code,
          new_password: newPassword,
        });
      }

      navigate("/login?passwordReset=1", {
        replace: true,
      });
    } catch (caught) {
      setError(resetErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <PublicRecoveryShell
      eyebrow="Sécurité du compte"
      title="Créez un nouveau mot de passe."
      description={
        magicMode
          ? "Votre lien sécurisé a été reconnu. Choisissez maintenant un nouveau mot de passe."
          : "Saisissez le code à 6 chiffres reçu par e-mail puis choisissez votre nouveau mot de passe."
      }
    >
      <Card className="w-full border-white/80 p-7 shadow-[0_24px_70px_rgba(14,42,77,0.12)] sm:p-8">
        <form noValidate onSubmit={submit} className="flex flex-col gap-5">
          {magicMode ? (
            <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-800">
              Lien sécurisé détecté. Vous n’avez pas besoin de recopier le code reçu par e-mail.
            </div>
          ) : (
            <>
              <div>
                <label
                  htmlFor="password-reset-email"
                  className="mb-2 block text-[13px] font-semibold text-navy"
                >
                  Adresse e-mail
                </label>

                <Input
                  id="password-reset-email"
                  type="email"
                  autoComplete="email"
                  inputMode="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="min-h-[50px] w-full"
                  placeholder="nom@exemple.fr"
                />
              </div>

              <div>
                <label
                  htmlFor="password-reset-code"
                  className="mb-2 block text-[13px] font-semibold text-navy"
                >
                  Code à 6 chiffres
                </label>

                <Input
                  id="password-reset-code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                  className="min-h-[50px] w-full font-mono text-lg tracking-[0.3em]"
                  placeholder="000000"
                />
              </div>
            </>
          )}

          <PasswordField
            id="password-reset-new"
            label="Nouveau mot de passe"
            value={newPassword}
            onChange={setNewPassword}
          />

          <PasswordField
            id="password-reset-confirmation"
            label="Confirmer le mot de passe"
            value={confirmation}
            confirmation
            onChange={setConfirmation}
          />

          {newPassword ? (
            <div className="grid gap-2 rounded-2xl border border-navy/10 bg-[#f7fafc] px-4 py-3 text-xs text-navy/60">
              <p className={hasMinimumLength ? "font-semibold text-emerald-700" : ""}>
                {hasMinimumLength ? "✓" : "○"} Au moins 10 caractères
              </p>
              <p className={notOnlyNumeric ? "font-semibold text-emerald-700" : ""}>
                {notOnlyNumeric ? "✓" : "○"} Pas uniquement des chiffres
              </p>
              <p className={passwordsMatch ? "font-semibold text-emerald-700" : ""}>
                {passwordsMatch ? "✓" : "○"} Les deux mots de passe correspondent
              </p>
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
            >
              {error}
            </div>
          ) : null}

          <Button
            type="submit"
            disabled={loading}
            className="min-h-[52px] w-full rounded-xl bg-gradient-to-r from-cyan to-primary font-semibold shadow-[0_12px_30px_rgba(22,99,199,0.25)]"
          >
            {loading ? "Réinitialisation…" : "Enregistrer le nouveau mot de passe"}
          </Button>

          <div className="flex flex-col gap-1 text-center">
            {!magicMode ? (
              <Link
                to="/forgot-password"
                className="inline-flex min-h-11 items-center justify-center rounded-xl text-sm font-semibold text-primary transition hover:bg-primary/5"
              >
                Recevoir un nouveau code
              </Link>
            ) : null}

            <Link
              to="/login"
              className="inline-flex min-h-11 items-center justify-center rounded-xl text-sm font-semibold text-navy/55 transition hover:bg-navy/5 hover:text-navy"
            >
              ← Retour à la connexion
            </Link>
          </div>
        </form>
      </Card>
    </PublicRecoveryShell>
  );
}
