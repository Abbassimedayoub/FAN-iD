import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { BrandMark } from "@/components/BrandMark";
import { Button, Card, Input } from "@/components/primitives";
import { useAuth } from "@/features/auth/AuthContext";

import { commissionPercentToRate } from "./commission";
import { completeOrganizerApplication, registerOrganizerAccount } from "./organizerRegistration";

const MINIMUM_AGE = 16;

function ageOnToday(dateString: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateString);

  if (!match) {
    return null;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);

  const birthDate = new Date(year, month - 1, day);

  if (
    birthDate.getFullYear() !== year ||
    birthDate.getMonth() !== month - 1 ||
    birthDate.getDate() !== day
  ) {
    return null;
  }

  const today = new Date();

  if (birthDate > today) {
    return -1;
  }

  let age = today.getFullYear() - year;

  const birthdayPassed =
    today.getMonth() > month - 1 || (today.getMonth() === month - 1 && today.getDate() >= day);

  if (!birthdayPassed) {
    age -= 1;
  }

  return age;
}

const accountSchema = z
  .object({
    firstName: z.string().trim().min(1, "Prénom requis.").max(150, "Prénom trop long."),
    lastName: z.string().trim().min(1, "Nom requis.").max(150, "Nom trop long."),
    dateOfBirth: z
      .string()
      .min(1, "Date de naissance requise.")
      .refine((value) => {
        const age = ageOnToday(value);
        return age !== null && age >= 0;
      }, "Date de naissance invalide.")
      .refine((value) => {
        const age = ageOnToday(value);
        return age !== null && age >= MINIMUM_AGE;
      }, `Vous devez avoir au moins ${MINIMUM_AGE} ans.`),
    phone: z.string().trim().max(32, "Numéro de téléphone trop long."),
    email: z
      .string()
      .trim()
      .min(1, "Adresse e-mail requise.")
      .max(254, "Adresse e-mail trop longue.")
      .email("Adresse e-mail invalide."),
    password: z
      .string()
      .min(10, "Le mot de passe doit contenir au moins 10 caractères.")
      .max(128, "Mot de passe trop long.")
      .refine(
        (value) => !/^\d+$/.test(value),
        "Le mot de passe ne peut pas être entièrement numérique.",
      ),
    passwordConfirmation: z.string().min(1, "Confirmez votre mot de passe."),
    termsAccepted: z
      .boolean()
      .refine((value) => value, "Vous devez accepter les conditions d’utilisation."),
  })
  .refine((values) => values.password === values.passwordConfirmation, {
    path: ["passwordConfirmation"],
    message: "Les mots de passe ne correspondent pas.",
  });

const organizationSchema = z.object({
  organizationName: z.string().trim().min(1, "Nom de l’organisation requis."),
  contactEmail: z
    .string()
    .trim()
    .min(1, "E-mail de contact requis.")
    .max(254, "Adresse e-mail trop longue.")
    .email("Adresse e-mail de contact invalide."),
  proposedCommissionPercent: z
    .string()
    .trim()
    .min(1, "Votre proposition de commission est obligatoire.")
    .refine((value) => {
      const normalized = value.replace(",", ".");

      if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) {
        return false;
      }

      const percent = Number(normalized);

      return Number.isFinite(percent) && percent >= 0 && percent <= 100;
    }, "Saisissez un pourcentage entre 0 et 100 avec au maximum deux décimales."),
  vatNumber: z.string().trim().max(32, "Numéro de TVA trop long."),
});

type AccountValues = z.infer<typeof accountSchema>;
type OrganizationValues = z.infer<typeof organizationSchema>;

interface StoredAccount {
  email: string;
  password: string;
}

function getErrorCode(error: unknown): string | null {
  if (typeof error !== "object" || error === null || !("code" in error)) {
    return null;
  }

  const code = (error as { code?: unknown }).code;
  return typeof code === "string" ? code : null;
}

function accountErrorMessage(error: unknown): string {
  switch (getErrorCode(error)) {
    case "EMAIL_ALREADY_EXISTS":
      return "Un compte existe déjà avec cette adresse e-mail.";
    case "INVALID_CREDENTIALS":
      return "Ce compte existe déjà, mais le mot de passe saisi est incorrect.";
    case "UNDERAGE":
      return "Vous devez avoir au moins 16 ans pour créer un compte.";
    case "TERMS_NOT_ACCEPTED":
      return "Vous devez accepter les conditions d’utilisation.";
    case "VALIDATION_ERROR":
      return "Certaines informations ne respectent pas les règles d’inscription. Vérifiez notamment le mot de passe.";
    case "RATE_LIMIT_EXCEEDED":
      return "Trop de tentatives d’inscription. Réessayez plus tard.";
    case "NETWORK_ERROR":
      return "Connexion au serveur impossible. Réessayez.";
    default:
      return "Impossible de créer le compte. Vérifiez les informations saisies.";
  }
}

function applicationErrorMessage(error: unknown): string {
  switch (getErrorCode(error)) {
    case "INVALID_CREDENTIALS":
      return "Le compte a été créé, mais la connexion automatique a échoué. Vérifiez le mot de passe puis réessayez.";
    case "ORGANIZER_ALREADY_EXISTS":
      return "Une demande organisateur existe déjà pour ce compte ou ce nom d’organisation est déjà utilisé.";
    case "RATE_LIMIT_EXCEEDED":
      return "Trop de tentatives. Réessayez plus tard.";
    case "NETWORK_ERROR":
      return "Connexion au serveur impossible. Votre compte est conservé : vous pouvez réessayer cette étape.";
    default:
      return "Impossible d’envoyer la demande organisateur. Votre compte est conservé et vous pouvez réessayer.";
  }
}

function FieldError({ id, message }: { id: string; message: string | undefined }) {
  if (!message) {
    return null;
  }

  return (
    <p id={id} role="alert" className="mt-2 text-xs font-medium text-red-600">
      {message}
    </p>
  );
}

function PasswordRule({
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
    <li
      className={[
        "flex items-start gap-2 transition-colors",
        active ? "text-emerald-700" : "text-navy/55",
      ].join(" ")}
    >
      <span
        aria-hidden="true"
        className={[
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold",
          active ? "bg-emerald-100 text-emerald-700" : "bg-navy/5 text-navy/45",
        ].join(" ")}
      >
        {active ? "✓" : serverOnly ? "◆" : "○"}
      </span>

      <span>{children}</span>
    </li>
  );
}

function PasswordEyeIcon({ visible }: { visible: boolean }) {
  if (visible) {
    return (
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
    );
  }

  return (
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
  );
}

function StepBadge({
  number,
  label,
  active,
  complete,
}: {
  number: number;
  label: string;
  active: boolean;
  complete: boolean;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span
        className={[
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold",
          active || complete ? "bg-primary text-white" : "bg-navy/8 text-navy/45",
        ].join(" ")}
      >
        {complete ? "✓" : number}
      </span>

      <div className="min-w-0">
        <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-navy/35">
          Étape {number}
        </p>
        <p
          className={["truncate text-sm font-semibold", active ? "text-navy" : "text-navy/55"].join(
            " ",
          )}
        >
          {label}
        </p>
      </div>
    </div>
  );
}

export function OrganizerRegistrationPage() {
  const navigate = useNavigate();
  const { authenticate } = useAuth();

  const [step, setStep] = useState<1 | 2>(1);
  const [storedAccount, setStoredAccount] = useState<StoredAccount | null>(null);
  const [accountApiError, setAccountApiError] = useState<string | null>(null);
  const [applicationApiError, setApplicationApiError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirmation, setShowPasswordConfirmation] = useState(false);

  const accountForm = useForm<AccountValues>({
    resolver: zodResolver(accountSchema),
    defaultValues: {
      firstName: "",
      lastName: "",
      dateOfBirth: "",
      phone: "",
      email: "",
      password: "",
      passwordConfirmation: "",
      termsAccepted: false,
    },
  });

  const password = accountForm.watch("password");
  const passwordConfirmation = accountForm.watch("passwordConfirmation");

  const hasMinimumLength = password.length >= 10;
  const isNotOnlyNumeric = password.length > 0 && !/^\d+$/.test(password);
  const confirmationMatches = passwordConfirmation.length > 0 && password === passwordConfirmation;

  const organizationForm = useForm<OrganizationValues>({
    resolver: zodResolver(organizationSchema),
    defaultValues: {
      organizationName: "",
      contactEmail: "",
      proposedCommissionPercent: "",
      vatNumber: "",
    },
  });

  const submitAccount = accountForm.handleSubmit(async (values) => {
    setAccountApiError(null);

    try {
      const accountUser = await registerOrganizerAccount({
        email: values.email.trim(),
        password: values.password,
        first_name: values.firstName.trim(),
        last_name: values.lastName.trim(),
        date_of_birth: values.dateOfBirth,
        terms_accepted: values.termsAccepted,
        ...(values.phone.trim() ? { phone: values.phone.trim() } : {}),
      });

      if (accountUser.role === "ORGANIZER") {
        authenticate(accountUser);

        navigate("/organizer", {
          replace: true,
          state: {
            existingOrganizerAccount: true,
          },
        });

        return;
      }

      setStoredAccount({
        email: values.email.trim(),
        password: values.password,
      });

      organizationForm.setValue("contactEmail", values.email.trim(), {
        shouldValidate: false,
      });

      setStep(2);
    } catch (error) {
      setAccountApiError(accountErrorMessage(error));
    }
  });

  const submitOrganization = organizationForm.handleSubmit(async (values) => {
    if (!storedAccount) {
      setStep(1);
      return;
    }

    setApplicationApiError(null);

    try {
      const result = await completeOrganizerApplication(storedAccount, {
        org_name: values.organizationName.trim(),
        contact_email: values.contactEmail.trim(),
        proposed_commission_rate: commissionPercentToRate(values.proposedCommissionPercent),
        ...(values.vatNumber.trim() ? { vat_number: values.vatNumber.trim() } : {}),
      });

      authenticate(result.user);
      navigate("/organizer", { replace: true });
    } catch (error) {
      setApplicationApiError(applicationErrorMessage(error));
    }
  });

  return (
    <main className="min-h-screen bg-[#eef4f9] p-4 sm:p-6 lg:p-8">
      <section className="mx-auto grid min-h-[calc(100vh-2rem)] w-full max-w-[1500px] overflow-hidden rounded-[28px] border border-white/70 bg-white shadow-[0_30px_90px_rgba(14,42,77,0.12)] sm:min-h-[calc(100vh-3rem)] lg:grid-cols-[0.82fr_1.18fr]">
        <aside className="relative hidden overflow-hidden bg-[#0b3157] px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-14 xl:py-14">
          <div
            className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full border border-cyan/10"
            aria-hidden="true"
          />
          <div
            className="pointer-events-none absolute -bottom-40 right-[-100px] h-[420px] w-[420px] rounded-full border border-cyan/10"
            aria-hidden="true"
          />

          <BrandMark className="relative z-10 text-white" />

          <div className="relative z-10 max-w-lg pb-10">
            <p className="mb-4 text-xs font-bold uppercase tracking-[0.18em] text-cyan">
              Rejoindre FANID
            </p>

            <h1 className="font-sora text-4xl font-bold leading-[1.12] tracking-[-0.03em] xl:text-5xl">
              Créez.
              <br />
              Vendez.
              <br />
              Sécurisez.
            </h1>

            <p className="mt-7 max-w-md text-sm leading-7 text-white/60">
              Créez votre compte organisateur et envoyez votre dossier de validation en quelques
              minutes.
            </p>

            <div className="mt-10 space-y-4 text-sm text-white/65">
              <p>✓ Compte professionnel sécurisé</p>
              <p>✓ Validation administrative du dossier</p>
              <p>✓ Accès à votre espace organisateur</p>
            </div>
          </div>

          <p className="relative z-10 text-xs text-white/35">FANID · Secure ticketing platform</p>
        </aside>

        <div className="flex items-start justify-center px-5 py-10 sm:px-10 lg:px-12 xl:px-16">
          <div className="w-full max-w-[720px]">
            <div className="mb-8 lg:hidden">
              <BrandMark className="text-navy" />
            </div>

            <div className="mb-7">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">
                Devenir organisateur
              </p>

              <h2 className="font-sora text-3xl font-bold tracking-[-0.03em] text-navy">
                Créez votre espace FANID.
              </h2>

              <p className="mt-3 text-sm leading-6 text-navy/55">
                Votre demande sera examinée par un administrateur avant l’activation complète de
                votre activité.
              </p>
            </div>

            <Card className="mb-6 grid gap-5 border-white/80 p-5 sm:grid-cols-2">
              <StepBadge
                number={1}
                label="Votre compte"
                active={step === 1}
                complete={step === 2}
              />

              <StepBadge
                number={2}
                label="Votre organisation"
                active={step === 2}
                complete={false}
              />
            </Card>

            {step === 1 ? (
              <Card className="border-white/80 p-6 shadow-[0_24px_70px_rgba(14,42,77,0.10)] sm:p-8">
                <form noValidate onSubmit={submitAccount} className="space-y-6">
                  <div>
                    <h3 className="font-sora text-xl font-bold text-navy">
                      Informations personnelles
                    </h3>
                    <p className="mt-1 text-sm text-navy/50">
                      Ces informations identifient le titulaire du compte.
                    </p>
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor="organizer-first-name"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Prénom
                      </label>
                      <Input
                        id="organizer-first-name"
                        autoComplete="given-name"
                        className="min-h-[50px] w-full"
                        aria-invalid={accountForm.formState.errors.firstName ? "true" : "false"}
                        {...accountForm.register("firstName")}
                      />
                      <FieldError
                        id="organizer-first-name-error"
                        message={accountForm.formState.errors.firstName?.message}
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="organizer-last-name"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Nom
                      </label>
                      <Input
                        id="organizer-last-name"
                        autoComplete="family-name"
                        className="min-h-[50px] w-full"
                        aria-invalid={accountForm.formState.errors.lastName ? "true" : "false"}
                        {...accountForm.register("lastName")}
                      />
                      <FieldError
                        id="organizer-last-name-error"
                        message={accountForm.formState.errors.lastName?.message}
                      />
                    </div>
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor="organizer-birth-date"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Date de naissance
                      </label>
                      <Input
                        id="organizer-birth-date"
                        type="date"
                        autoComplete="bday"
                        className="min-h-[50px] w-full"
                        aria-invalid={accountForm.formState.errors.dateOfBirth ? "true" : "false"}
                        {...accountForm.register("dateOfBirth")}
                      />
                      <FieldError
                        id="organizer-birth-date-error"
                        message={accountForm.formState.errors.dateOfBirth?.message}
                      />
                    </div>

                    <div>
                      <label
                        htmlFor="organizer-phone"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Téléphone <span className="font-normal text-navy/40">(facultatif)</span>
                      </label>
                      <Input
                        id="organizer-phone"
                        type="tel"
                        autoComplete="tel"
                        className="min-h-[50px] w-full"
                        {...accountForm.register("phone")}
                      />
                      <FieldError
                        id="organizer-phone-error"
                        message={accountForm.formState.errors.phone?.message}
                      />
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="organizer-email"
                      className="mb-2 block text-[13px] font-semibold text-navy"
                    >
                      Adresse e-mail
                    </label>
                    <Input
                      id="organizer-email"
                      type="email"
                      autoComplete="email"
                      className="min-h-[50px] w-full"
                      placeholder="contact@organisation.fr"
                      aria-invalid={accountForm.formState.errors.email ? "true" : "false"}
                      {...accountForm.register("email")}
                    />
                    <FieldError
                      id="organizer-email-error"
                      message={accountForm.formState.errors.email?.message}
                    />
                  </div>

                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <label
                        htmlFor="organizer-password"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Mot de passe
                      </label>
                      <div className="relative">
                        <Input
                          id="organizer-password"
                          type={showPassword ? "text" : "password"}
                          autoComplete="new-password"
                          maxLength={128}
                          placeholder="••••••••••••"
                          aria-invalid={accountForm.formState.errors.password ? "true" : "false"}
                          aria-describedby={
                            accountForm.formState.errors.password
                              ? "organizer-password-error organizer-password-rules"
                              : "organizer-password-rules"
                          }
                          className="w-full pr-14"
                          {...accountForm.register("password")}
                        />

                        <button
                          type="button"
                          onClick={() => setShowPassword((visible) => !visible)}
                          aria-label={
                            showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"
                          }
                          aria-pressed={showPassword}
                          aria-controls="organizer-password"
                          className="absolute right-1 top-1/2 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-lg text-navy/60 transition hover:bg-navy/5 hover:text-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                        >
                          <PasswordEyeIcon visible={showPassword} />
                        </button>
                      </div>
                      <FieldError
                        id="organizer-password-error"
                        message={accountForm.formState.errors.password?.message}
                      />
                      <div
                        id="organizer-password-rules"
                        className="mt-4 rounded-2xl border border-[#e2e9f0] bg-[#f8fafc] p-4"
                      >
                        <p className="text-xs font-bold uppercase tracking-[0.12em] text-navy/55">
                          Conditions du mot de passe
                        </p>

                        <ul className="mt-3 space-y-2 text-sm">
                          <PasswordRule valid={hasMinimumLength}>
                            Contenir au moins 10 caractères.
                          </PasswordRule>

                          <PasswordRule valid={isNotOnlyNumeric}>
                            Ne pas être entièrement numérique.
                          </PasswordRule>

                          <PasswordRule serverOnly>
                            Ne pas être trop similaire à votre adresse e-mail, votre prénom ou votre
                            nom.
                          </PasswordRule>

                          <PasswordRule serverOnly>
                            Ne pas être un mot de passe couramment utilisé.
                          </PasswordRule>
                        </ul>

                        <p className="mt-4 text-xs leading-5 text-navy/40">
                          ◆ Vérifié exactement par Django lors de la création du compte.
                        </p>
                      </div>
                    </div>

                    <div>
                      <label
                        htmlFor="organizer-password-confirmation"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Confirmer le mot de passe
                      </label>
                      <div className="relative">
                        <Input
                          id="organizer-password-confirmation"
                          type={showPasswordConfirmation ? "text" : "password"}
                          autoComplete="new-password"
                          maxLength={128}
                          placeholder="••••••••••••"
                          aria-invalid={
                            accountForm.formState.errors.passwordConfirmation ? "true" : "false"
                          }
                          aria-describedby={
                            [
                              accountForm.formState.errors.passwordConfirmation
                                ? "organizer-password-confirmation-error"
                                : null,
                              passwordConfirmation.length > 0
                                ? "organizer-password-confirmation-status"
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" ") || undefined
                          }
                          className="w-full pr-14"
                          {...accountForm.register("passwordConfirmation")}
                        />

                        <button
                          type="button"
                          onClick={() => setShowPasswordConfirmation((visible) => !visible)}
                          aria-label={
                            showPasswordConfirmation
                              ? "Masquer la confirmation du mot de passe"
                              : "Afficher la confirmation du mot de passe"
                          }
                          aria-pressed={showPasswordConfirmation}
                          aria-controls="organizer-password-confirmation"
                          className="absolute right-1 top-1/2 flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center rounded-lg text-navy/60 transition hover:bg-navy/5 hover:text-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                        >
                          <PasswordEyeIcon visible={showPasswordConfirmation} />
                        </button>
                      </div>
                      <FieldError
                        id="organizer-password-confirmation-error"
                        message={accountForm.formState.errors.passwordConfirmation?.message}
                      />
                      {passwordConfirmation.length > 0 ? (
                        <p
                          id="organizer-password-confirmation-status"
                          className={[
                            "mt-2 text-xs font-semibold",
                            confirmationMatches ? "text-emerald-700" : "text-amber-700",
                          ].join(" ")}
                        >
                          {confirmationMatches
                            ? "✓ Les deux mots de passe correspondent."
                            : "○ Les deux mots de passe ne correspondent pas encore."}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-navy/10 bg-navy/[0.025] p-4">
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded border-navy/20"
                      {...accountForm.register("termsAccepted")}
                    />
                    <span className="text-sm leading-6 text-navy/65">
                      J’accepte les conditions d’utilisation et confirme que les informations
                      fournies sont exactes.
                    </span>
                  </label>

                  <FieldError
                    id="organizer-terms-error"
                    message={accountForm.formState.errors.termsAccepted?.message}
                  />

                  {accountApiError ? (
                    <div
                      role="alert"
                      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium leading-6 text-red-700"
                    >
                      {accountApiError}
                    </div>
                  ) : null}

                  <Button
                    type="submit"
                    disabled={accountForm.formState.isSubmitting}
                    className="min-h-[52px] w-full rounded-xl bg-gradient-to-r from-cyan to-primary font-semibold"
                  >
                    {accountForm.formState.isSubmitting
                      ? "Création du compte…"
                      : "Continuer vers l’organisation"}
                  </Button>
                </form>
              </Card>
            ) : (
              <Card className="border-white/80 p-6 shadow-[0_24px_70px_rgba(14,42,77,0.10)] sm:p-8">
                <form noValidate onSubmit={submitOrganization} className="space-y-6">
                  <div>
                    <h3 className="font-sora text-xl font-bold text-navy">Votre organisation</h3>
                    <p className="mt-1 text-sm leading-6 text-navy/50">
                      Ces informations constitueront votre dossier de validation FANID.
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="organization-name"
                      className="mb-2 block text-[13px] font-semibold text-navy"
                    >
                      Nom de l’organisation
                    </label>
                    <Input
                      id="organization-name"
                      className="min-h-[50px] w-full"
                      placeholder="Stade, club, association…"
                      aria-invalid={
                        organizationForm.formState.errors.organizationName ? "true" : "false"
                      }
                      {...organizationForm.register("organizationName")}
                    />
                    <FieldError
                      id="organization-name-error"
                      message={organizationForm.formState.errors.organizationName?.message}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="organization-contact-email"
                      className="mb-2 block text-[13px] font-semibold text-navy"
                    >
                      E-mail de contact
                    </label>
                    <Input
                      id="organization-contact-email"
                      type="email"
                      autoComplete="email"
                      className="min-h-[50px] w-full"
                      aria-invalid={
                        organizationForm.formState.errors.contactEmail ? "true" : "false"
                      }
                      {...organizationForm.register("contactEmail")}
                    />
                    <FieldError
                      id="organization-contact-email-error"
                      message={organizationForm.formState.errors.contactEmail?.message}
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="organization-vat"
                      className="mb-2 block text-[13px] font-semibold text-navy"
                    >
                      Numéro de TVA <span className="font-normal text-navy/40">(facultatif)</span>
                    </label>
                    <Input
                      id="organization-vat"
                      className="min-h-[50px] w-full"
                      placeholder="FR123456789"
                      {...organizationForm.register("vatNumber")}
                    />
                    <FieldError
                      id="organization-vat-error"
                      message={organizationForm.formState.errors.vatNumber?.message}
                    />
                  </div>

                  <div className="rounded-2xl border border-cyan/20 bg-cyan/5 p-4">
                    <p className="text-sm font-semibold text-navy">Après l’envoi</p>
                    <p className="mt-1 text-xs leading-5 text-navy/55">
                      Votre dossier sera créé avec le statut « En attente ». Un administrateur
                      pourra ensuite l’approuver ou le rejeter.
                    </p>
                  </div>

                  {applicationApiError ? (
                    <div
                      role="alert"
                      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium leading-6 text-red-700"
                    >
                      {applicationApiError}
                    </div>
                  ) : null}

                  <div className="flex flex-col-reverse gap-3 sm:flex-row">
                    <Button
                      type="button"
                      disabled={organizationForm.formState.isSubmitting}
                      onClick={() => {
                        setApplicationApiError(null);
                        setStep(1);
                      }}
                      className="min-h-[50px] flex-1"
                    >
                      Retour
                    </Button>

                    <div>
                      <label
                        htmlFor="organizer-proposed-commission"
                        className="mb-2 block text-[13px] font-semibold text-navy"
                      >
                        Proposition de commission FANID (%)
                      </label>

                      <div className="relative">
                        <Input
                          id="organizer-proposed-commission"
                          type="number"
                          min="0"
                          max="100"
                          step="0.01"
                          inputMode="decimal"
                          placeholder="12"
                          className="min-h-[50px] w-full pr-12"
                          aria-invalid={
                            organizationForm.formState.errors.proposedCommissionPercent
                              ? "true"
                              : "false"
                          }
                          {...organizationForm.register("proposedCommissionPercent")}
                        />

                        <span
                          aria-hidden="true"
                          className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-sm font-semibold text-navy/45"
                        >
                          %
                        </span>
                      </div>

                      <p className="mt-2 text-xs leading-5 text-navy/45">
                        Cette proposition ouvre la négociation avec FANID. L’approbation de votre
                        compte et l’accord de commission restent deux décisions distinctes.
                      </p>

                      <FieldError
                        id="organizer-proposed-commission-error"
                        message={
                          organizationForm.formState.errors.proposedCommissionPercent?.message
                        }
                      />
                    </div>

                    <Button
                      type="submit"
                      disabled={organizationForm.formState.isSubmitting}
                      className="min-h-[52px] flex-[1.4] rounded-xl bg-gradient-to-r from-cyan to-primary font-semibold"
                    >
                      {organizationForm.formState.isSubmitting
                        ? "Envoi de la demande…"
                        : "Créer mon espace organisateur"}
                    </Button>
                  </div>
                </form>
              </Card>
            )}

            <p className="mt-6 text-center text-sm text-navy/55">
              Vous avez déjà un compte ?{" "}
              <Link to="/login" className="font-semibold text-primary hover:underline">
                Se connecter
              </Link>
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
