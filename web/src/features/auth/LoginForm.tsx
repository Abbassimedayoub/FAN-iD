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
    <Card className="w-full max-w-md">
      <form noValidate onSubmit={submit} className="flex flex-col gap-4">
        <div>
          <label htmlFor="login-email" className="mb-1 block text-sm font-medium text-navy">
            Adresse e-mail
          </label>
          <Input
            id="login-email"
            type="email"
            autoComplete="email"
            aria-invalid={errors.email ? "true" : "false"}
            aria-describedby={errors.email ? "login-email-error" : undefined}
            className="min-h-[48px] w-full"
            {...register("email")}
          />
          {errors.email ? (
            <p id="login-email-error" role="alert" className="mt-1 text-sm text-red-700">
              {errors.email.message}
            </p>
          ) : null}
        </div>

        <div>
          <label htmlFor="login-password" className="mb-1 block text-sm font-medium text-navy">
            Mot de passe
          </label>
          <Input
            id="login-password"
            type="password"
            autoComplete="current-password"
            aria-invalid={errors.password ? "true" : "false"}
            aria-describedby={errors.password ? "login-password-error" : undefined}
            className="min-h-[48px] w-full"
            {...register("password")}
          />
          {errors.password ? (
            <p id="login-password-error" role="alert" className="mt-1 text-sm text-red-700">
              {errors.password.message}
            </p>
          ) : null}
        </div>

        {apiError ? (
          <p role="alert" className="text-sm font-medium text-red-700">
            {apiError}
          </p>
        ) : null}

        <Button type="submit" disabled={isSubmitting} className="min-h-[48px] w-full">
          {isSubmitting ? "Connexion…" : "Se connecter"}
        </Button>
      </form>
    </Card>
  );
}
