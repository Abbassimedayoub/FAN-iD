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

          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            placeholder="••••••••••••"
            aria-invalid={errors.password ? "true" : "false"}
            aria-describedby={errors.password ? "login-password-error" : undefined}
            className="min-h-[50px] w-full"
            {...register("password")}
          />

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
          <span className="text-xs font-semibold text-primary">Mot de passe oublié ?</span>
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
