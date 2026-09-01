import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { Button, Card, Input } from "@/components/primitives";

import { PublicRecoveryShell } from "./PublicRecoveryShell";
import { requestPasswordReset } from "./passwordReset";

function requestErrorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (error as { code?: unknown }).code;

    if (code === "RATE_LIMIT_EXCEEDED") {
      return "Trop de demandes ont été effectuées. Réessayez un peu plus tard.";
    }

    if (code === "VALIDATION_ERROR") {
      return "Vérifiez l’adresse e-mail saisie.";
    }
  }

  return "Impossible d’envoyer l’e-mail pour le moment. Réessayez.";
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sentEmail, setSentEmail] = useState("");
  const [expiresInSeconds, setExpiresInSeconds] = useState(900);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sent = sentEmail.length > 0;

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const normalizedEmail = email.trim();

    if (!normalizedEmail) {
      setError("Adresse e-mail requise.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await requestPasswordReset(normalizedEmail);
      setSentEmail(normalizedEmail);
      setExpiresInSeconds(result.expires_in_seconds);
    } catch (caught) {
      setError(requestErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  async function resend(): Promise<void> {
    if (!sentEmail || loading) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await requestPasswordReset(sentEmail);
      setExpiresInSeconds(result.expires_in_seconds);
    } catch (caught) {
      setError(requestErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  const minutes = Math.max(1, Math.round(expiresInSeconds / 60));

  return (
    <PublicRecoveryShell
      eyebrow="Récupération du compte"
      title={sent ? "Vérifiez votre boîte mail." : "Mot de passe oublié ?"}
      description={
        sent
          ? "Nous avons traité votre demande. Vous pouvez utiliser le bouton reçu par e-mail ou le code à 6 chiffres."
          : "Saisissez l’adresse e-mail liée à votre compte FANID. Le parcours est identique pour tous les comptes."
      }
    >
      <Card className="w-full border-white/80 p-7 shadow-[0_24px_70px_rgba(14,42,77,0.12)] sm:p-8">
        {!sent ? (
          <form noValidate onSubmit={submit} className="flex flex-col gap-5">
            <div>
              <label
                htmlFor="forgot-password-email"
                className="mb-2 block text-[13px] font-semibold text-navy"
              >
                Adresse e-mail
              </label>

              <Input
                id="forgot-password-email"
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="nom@exemple.fr"
                className="min-h-[50px] w-full"
              />
            </div>

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
              {loading ? "Envoi…" : "Recevoir le lien et le code"}
            </Button>

            <Link
              to="/login"
              className="inline-flex min-h-11 items-center justify-center rounded-xl text-sm font-semibold text-navy/55 transition hover:bg-navy/5 hover:text-navy"
            >
              ← Retour à la connexion
            </Link>
          </form>
        ) : (
          <div className="flex flex-col gap-5">
            <div
              role="status"
              className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4"
            >
              <p className="font-semibold text-emerald-900">Consultez votre boîte e-mail</p>
              <p className="mt-1 text-sm leading-6 text-emerald-800">
                Si un compte FANID correspond à cette adresse, vous recevrez un lien sécurisé et un
                code à 6 chiffres. Ils restent valables environ {minutes} minutes.
              </p>
            </div>

            <div className="rounded-2xl border border-navy/10 bg-[#f7fafc] px-5 py-4">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-navy/40">
                Adresse utilisée
              </p>
              <p className="mt-2 break-all text-sm font-semibold text-navy">{sentEmail}</p>
            </div>

            {error ? (
              <div
                role="alert"
                className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
              >
                {error}
              </div>
            ) : null}

            <Link
              to="/password-reset"
              state={{ email: sentEmail }}
              className="inline-flex min-h-[52px] items-center justify-center rounded-xl bg-gradient-to-r from-cyan to-primary px-5 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(22,99,199,0.25)] transition hover:-translate-y-0.5"
            >
              J’ai reçu mon code à 6 chiffres
            </Link>

            <button
              type="button"
              disabled={loading}
              onClick={resend}
              className="min-h-11 rounded-xl px-4 text-sm font-semibold text-primary transition hover:bg-primary/5 disabled:opacity-50"
            >
              {loading ? "Nouvel envoi…" : "Renvoyer l’e-mail"}
            </button>

            <Link
              to="/login"
              className="inline-flex min-h-11 items-center justify-center rounded-xl text-sm font-semibold text-navy/55 transition hover:bg-navy/5 hover:text-navy"
            >
              ← Retour à la connexion
            </Link>
          </div>
        )}
      </Card>
    </PublicRecoveryShell>
  );
}
