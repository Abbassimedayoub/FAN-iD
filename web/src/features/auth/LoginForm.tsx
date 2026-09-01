import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button, Card, Input } from "@/components/primitives";

import { loginWeb } from "./login";
import type { AuthUser } from "./types";

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Adresse e-mail requise.")
    .max(254, "Adresse e-mail trop longue.")
    .email("Adresse e-mail invalide."),
  password: z.string().min(1, "Mot de passe requis.").max(128, "Mot de passe trop long."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  INVALID_CREDENTIALS: "Adresse e-mail ou mot de passe incorrect.",
  DEVICE_LOCKED: "Ce compte est lié à un autre appareil.",
  VALIDATION_ERROR: "Vérifiez les informations saisies.",
  RATE_LIMIT_EXCEEDED: "Trop de tentatives. Réessayez plus tard.",
};

function loginErrorMessage(error: unknown): string {
  if (typeof error !== "object" || error === null || !("code" in error)) {
    return "Connexion impossible. Réessayez.";
  }

  const code = (error as { code?: unknown }).code;

  if (typeof code !== "string") {
    return "Connexion impossible. Réessayez.";
  }

  return LOGIN_ERROR_MESSAGES[code] ?? "Connexion impossible. Réessayez.";
}

interface LoginFormProps {
  onSuccess?: (user: AuthUser) => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [apiError, setApiError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const submit = handleSubmit(async (values) => {
    setApiError(null);

    try {
      const result = await loginWeb(values);
      onSuccess?.(result.user);
    } catch (error) {
      setApiError(loginErrorMessage(error));
    }
  });

  return (
    <Card className="w-full border-white/80 p-7 shadow-[0_24px_70px_rgba(14,42,77,0.12)] sm:p-8">
      <form noValidate onSubmit={submit} className="flex flex-col gap-5">
        <div>
          <label htmlFor="login-email" className="mb-2 block text-[13px] font-semibold text-navy">
            Adresse e-mail
          </label>

          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            placeholder="billetterie@om.fr"
            aria-invalid={errors.email ? "true" : "false"}
            aria-describedby={errors.email ? "login-email-error" : undefined}
            className="min-h-[50px] w-full"
            {...register("email")}
          />

          {errors.email ? (
            <p
              id="login-email-error"
              role="alert"
              className="mt-2 text-xs font-medium text-red-600"
            >
              {errors.email.message}
            </p>
          ) : null}
        </div>

        <div>
          <label
            htmlFor="login-password"
            className="mb-2 block text-[13px] font-semibold text-navy"
          >
            Mot de passe
          </label>

          <div className="relative">
            <Input
              id="login-password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="••••••••••••"
              aria-invalid={errors.password ? "true" : "false"}
              aria-describedby={errors.password ? "login-password-error" : undefined}
              className="min-h-[50px] w-full pr-14"
              {...register("password")}
            />

            <button
              type="button"
              onClick={() => setShowPassword((visible) => !visible)}
              aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
              aria-pressed={showPassword}
              aria-controls="login-password"
              className="absolute right-1 top-1/2 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-lg text-navy/60 transition hover:bg-navy/5 hover:text-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              {showPassword ? (
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

          {errors.password ? (
            <p
              id="login-password-error"
              role="alert"
              className="mt-2 text-xs font-medium text-red-600"
            >
              {errors.password.message}
            </p>
          ) : null}
        </div>

        <div className="-mt-2 flex justify-end">
          <a
            href="/forgot-password"
            className="inline-flex min-h-11 items-center rounded-lg px-2 text-xs font-semibold text-primary transition hover:bg-primary/5 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            Mot de passe oublié ?
          </a>
        </div>

        {apiError ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
          >
            {apiError}
          </div>
        ) : null}

        <Button
          type="submit"
          disabled={isSubmitting}
          className="min-h-[52px] w-full rounded-xl bg-gradient-to-r from-cyan to-primary font-semibold shadow-[0_12px_30px_rgba(22,99,199,0.25)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(22,99,199,0.32)]"
        >
          {isSubmitting ? "Connexion…" : "Se connecter"}
        </Button>

        <p className="pt-1 text-center text-xs text-navy/55">
          Pas encore de compte ?{" "}
          <a href="/register/organizer" className="font-semibold text-primary hover:underline">
            Devenir organisateur
          </a>
        </p>
      </form>
    </Card>
  );
}
