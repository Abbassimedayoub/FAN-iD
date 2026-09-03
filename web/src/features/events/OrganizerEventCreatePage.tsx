import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";

import { Button, Card, Input, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";
import { fetchMyOrganizer, myOrganizerQueryKey } from "@/features/organizers/myOrganizer";

import { OrganizerEventCategoriesStep } from "./OrganizerEventCategoriesStep";
import { OrganizerEventCategoryField } from "./OrganizerEventCategoryField";
import { OrganizerEventPublicationStep } from "./OrganizerEventPublicationStep";
import { createEventDraft, fetchEventCategories, updateEventDraft, uploadEventImage } from "./api";
import type { EventDraftInput, OrganizerEvent } from "./types";
import { endTimeThreeHoursAfter } from "./eventScheduleDefaults";
import { isEventDateAtLeastTomorrow, minimumEventDate } from "./eventScheduleDefaults";
import { eventImageUrl } from "./eventImageUrl";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const eventInformationSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, "Le nom de l’événement est requis.")
      .max(160, "Le nom est trop long."),
    description: z.string().max(5000, "La description est trop longue."),
    categoryId: z.string().min(1, "Sélectionnez une catégorie."),
    eventDate: z.string().min(1, "La date est requise."),
    startTime: z.string().min(1, "L’heure de début est requise."),
    endTime: z.string().min(1, "L’heure de fin est requise."),
    capacityTotal: z.string(),
    venue: z.string().max(240, "Le lieu est trop long."),
  })
  .superRefine((values, context) => {
    if (values.capacityTotal.trim() !== "") {
      const capacity = Number(values.capacityTotal);

      if (!Number.isInteger(capacity) || capacity < 1) {
        context.addIssue({
          code: "custom",
          path: ["capacityTotal"],
          message: "La capacité doit être un entier positif.",
        });
      }
    }

    if (values.eventDate && values.startTime && values.endTime) {
      const start = new Date(`${values.eventDate}T${values.startTime}:00`);

      const end = new Date(`${values.eventDate}T${values.endTime}:00`);

      if (Number.isFinite(start.getTime()) && Number.isFinite(end.getTime()) && end <= start) {
        context.addIssue({
          code: "custom",
          path: ["endTime"],
          message: "L’heure de fin doit être postérieure au début.",
        });
      }
    }
  });

type EventInformationValues = z.infer<typeof eventInformationSchema>;

function FieldError({ message }: { message?: string }) {
  if (!message) {
    return null;
  }

  return (
    <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
      {message}
    </p>
  );
}

function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = (
      error as {
        code?: unknown;
      }
    ).code;

    switch (code) {
      case "EVENT_ALREADY_EXISTS":
      case "CONFLICT":
        return "Un événement avec ces informations existe déjà.";
      case "STALE_RESOURCE":
        return "Le brouillon a été modifié ailleurs. Rechargez la page avant de réessayer.";
      case "ORGANIZER_NOT_APPROVED":
        return "Votre organisation doit être approuvée avant de gérer des événements.";
      case "VALIDATION_ERROR":
        return "Certaines informations ne respectent pas les règles de l’événement.";
      case "NETWORK_ERROR":
        return "Connexion au serveur impossible. Réessayez.";
    }
  }

  return "Impossible d’enregistrer le brouillon. Réessayez.";
}

function toPayload(values: EventInformationValues): EventDraftInput {
  const start = new Date(`${values.eventDate}T${values.startTime}:00`);

  const end = new Date(`${values.eventDate}T${values.endTime}:00`);

  return {
    category_id: values.categoryId,
    name: values.name.trim(),
    description: values.description.trim(),
    starts_at: start.toISOString(),
    ends_at: end.toISOString(),
    venue: values.venue.trim(),
    capacity_total: values.capacityTotal.trim() === "" ? null : Number(values.capacityTotal),
  };
}

function StepIndicator({
  number,
  label,
  active,
  complete = false,
}: {
  number: number;
  label: string;
  active: boolean;
  complete?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <span
        className={[
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold",
          active || complete
            ? "bg-[#1769d2] text-white"
            : "border border-[#d8e0e8] bg-white text-[#8492a3]",
        ].join(" ")}
      >
        {complete ? "✓" : number}
      </span>

      <span
        className={[
          "truncate text-sm font-semibold",
          active ? "text-[#23354d]" : complete ? "text-[#1769d2]" : "text-[#8c98a7]",
        ].join(" ")}
      >
        {label}
      </span>
    </div>
  );
}

export function OrganizerEventCreatePage() {
  const navigate = useNavigate();

  const minimumDate = minimumEventDate();

  const [step, setStep] = useState<1 | 2 | 3>(1);

  const [savedEvent, setSavedEvent] = useState<OrganizerEvent | null>(null);

  const [selectedImage, setSelectedImage] = useState<File | null>(null);

  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const [imageError, setImageError] = useState<string | null>(null);

  const [apiError, setApiError] = useState<string | null>(null);

  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const organizerQuery = useQuery({
    queryKey: myOrganizerQueryKey,
    queryFn: fetchMyOrganizer,
  });

  const categoriesQuery = useQuery({
    queryKey: ["catalog", "event-categories"],
    queryFn: fetchEventCategories,
    enabled: organizerQuery.data?.validation_status === "APPROVED",
  });

  const form = useForm<EventInformationValues>({
    resolver: zodResolver(eventInformationSchema),
    defaultValues: {
      name: "",
      description: "",
      categoryId: "",
      eventDate: "",
      startTime: "",
      endTime: "",
      capacityTotal: "",
      venue: "",
    },
  });

  useEffect(() => {
    return () => {
      if (imagePreview?.startsWith("blob:")) {
        URL.revokeObjectURL(imagePreview);
      }
    };
  }, [imagePreview]);

  const categoryOptions = useMemo(() => categoriesQuery.data ?? [], [categoriesQuery.data]);

  const selectedCategoryId = form.watch("categoryId");

  function selectImage(file: File | undefined): void {
    setImageError(null);

    if (!file) {
      setSelectedImage(null);
      return;
    }

    if (!["image/png", "image/jpeg"].includes(file.type)) {
      setImageError("Utilisez une image PNG ou JPG.");
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setImageError("L’image ne doit pas dépasser 5 Mo.");
      return;
    }

    if (imagePreview?.startsWith("blob:")) {
      URL.revokeObjectURL(imagePreview);
    }

    setSelectedImage(file);
    setImagePreview(URL.createObjectURL(file));
  }

  async function persistInformation(
    values: EventInformationValues,
    advance: boolean,
  ): Promise<void> {
    if (!isEventDateAtLeastTomorrow(values.eventDate)) {
      form.setError("eventDate", {
        type: "validate",
        message: "La date de l’événement doit être au minimum demain.",
      });
      return;
    }

    form.clearErrors("eventDate");

    setApiError(null);
    setSuccessMessage(null);

    try {
      const payload = toPayload(values);

      let event = savedEvent
        ? await updateEventDraft(savedEvent, payload)
        : await createEventDraft(payload);

      setSavedEvent(event);

      if (selectedImage) {
        try {
          event = await uploadEventImage(event, selectedImage);

          setSavedEvent(event);
          setSelectedImage(null);

          if (event.image_url) {
            if (imagePreview?.startsWith("blob:")) {
              URL.revokeObjectURL(imagePreview);
            }

            setImagePreview(eventImageUrl(event.image_url));
          }
        } catch (error) {
          setApiError(
            `${errorMessage(error)} Le brouillon a toutefois bien été enregistré sans la nouvelle image.`,
          );
          return;
        }
      }

      if (advance) {
        setStep(2);
        setSuccessMessage(null);
      } else {
        setSuccessMessage("Brouillon enregistré.");
      }
    } catch (error) {
      setApiError(errorMessage(error));
    }
  }

  const saveInformation = form.handleSubmit(async (values) => {
    await persistInformation(values, false);
  });

  const continueInformation = form.handleSubmit(async (values) => {
    await persistInformation(values, true);
  });

  const breadcrumbs = (
    <div className="flex items-center gap-2 text-sm">
      <Link to="/organizer" className="font-medium text-[#8a96a5] transition hover:text-[#1769d2]">
        Événements
      </Link>

      <span aria-hidden="true" className="text-[#b4bdc8]">
        /
      </span>

      <span className="font-semibold text-[#34465c]">Nouvel événement</span>
    </div>
  );

  if (organizerQuery.isPending) {
    return (
      <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
        <div className="flex min-h-[520px] items-center justify-center">
          <Spinner label="Chargement de l’espace organisateur" />
        </div>
      </OrganizerShell>
    );
  }

  if (organizerQuery.isError || !organizerQuery.data) {
    return (
      <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
        <main className="p-6 lg:p-10">
          <Card className="mx-auto max-w-xl p-8 text-center">
            <h1 className="font-sora text-2xl font-bold text-navy">
              Espace organisateur indisponible
            </h1>
            <p className="mt-3 text-sm leading-6 text-navy/55">
              Impossible de charger votre dossier organisateur.
            </p>
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  if (organizerQuery.data.validation_status !== "APPROVED") {
    return (
      <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
        <main className="p-6 lg:p-10">
          <Card className="mx-auto max-w-xl p-8 text-center">
            <h1 className="font-sora text-2xl font-bold text-navy">
              Gestion des événements indisponible
            </h1>
            <p className="mt-3 text-sm leading-6 text-navy/55">
              Votre organisation doit être approuvée avant de créer ou gérer des événements.
            </p>
            <Link
              to="/organizer"
              className="mt-6 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
            >
              Retour au tableau de bord
            </Link>
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  return (
    <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[1060px]">
          <div className="mb-7">
            <h1 className="font-sora text-[28px] font-bold tracking-[-0.025em] text-[#26384f]">
              Créer un événement
            </h1>

            <p className="mt-2 text-sm text-[#778596]">
              Configurez les informations essentielles de votre événement.
            </p>
          </div>

          <div className="mb-6 rounded-2xl border border-[#e1e7ed] bg-white px-5 py-5 shadow-sm sm:px-7">
            <div className="flex items-center">
              <StepIndicator
                number={1}
                label="Informations"
                active={step === 1}
                complete={step > 1}
              />

              <div aria-hidden="true" className="mx-4 hidden h-px flex-1 bg-[#dfe5eb] sm:block" />

              <StepIndicator number={2} label="Catégories & quotas" active={step === 2} />

              <div aria-hidden="true" className="mx-4 hidden h-px flex-1 bg-[#dfe5eb] sm:block" />

              <StepIndicator number={3} label="Publication" active={step === 3} />
            </div>
          </div>

          {step === 1 ? (
            <form noValidate onSubmit={saveInformation}>
              <Card className="overflow-hidden border-[#e1e7ed] p-0 shadow-[0_10px_28px_rgba(23,45,74,0.05)]">
                <div className="border-b border-[#edf0f3] px-6 py-5 sm:px-8">
                  <h2 className="font-sora text-lg font-bold text-[#26384f]">
                    Informations générales
                  </h2>
                  <p className="mt-1 text-sm text-[#8591a0]">
                    Ces informations seront visibles par vos participants.
                  </p>
                </div>

                <div className="space-y-6 px-6 py-6 sm:px-8 sm:py-7">
                  <div>
                    <label
                      htmlFor="event-name"
                      className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                    >
                      Nom de l’événement
                    </label>

                    <Input
                      id="event-name"
                      className="w-full"
                      placeholder="Ex. Derby FANID 2026"
                      aria-invalid={form.formState.errors.name ? "true" : "false"}
                      {...form.register("name")}
                    />

                    <FieldError message={form.formState.errors.name?.message} />
                  </div>

                  <div>
                    <label
                      htmlFor="event-description"
                      className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                    >
                      Description
                    </label>

                    <textarea
                      id="event-description"
                      rows={4}
                      placeholder="Décrivez votre événement..."
                      className="w-full resize-y rounded-xl border border-[#d7e0e9] bg-white px-4 py-3 text-sm text-navy shadow-sm outline-none transition placeholder:text-navy/30 hover:border-navy/25 focus:border-cyan focus:ring-4 focus:ring-cyan/10"
                      {...form.register("description")}
                    />

                    <div className="mt-1 flex justify-between gap-4">
                      <FieldError message={form.formState.errors.description?.message} />

                      <span className="ml-auto text-[11px] text-[#9aa5b1]">
                        Présentez les informations utiles aux participants.
                      </span>
                    </div>
                  </div>

                  <OrganizerEventCategoryField
                    categories={categoryOptions}
                    isPending={categoriesQuery.isPending}
                    isError={categoriesQuery.isError}
                    value={selectedCategoryId}
                    validationMessage={form.formState.errors.categoryId?.message}
                    onChange={(categoryId) => {
                      form.setValue("categoryId", categoryId, {
                        shouldDirty: true,
                        shouldValidate: true,
                      });
                    }}
                  />

                  <div className="grid gap-5 md:grid-cols-3">
                    <div>
                      <label
                        htmlFor="event-date"
                        className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                      >
                        Date
                      </label>

                      <Input
                        id="event-date"
                        type="date"
                        min={minimumDate}
                        className="w-full"
                        {...form.register("eventDate")}
                      />

                      <FieldError message={form.formState.errors.eventDate?.message} />
                    </div>

                    <div>
                      <label
                        htmlFor="event-start-time"
                        className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                      >
                        Heure de début
                      </label>

                      <Input
                        id="event-start-time"
                        type="time"
                        className="w-full"
                        {...form.register("startTime")}
                        onChange={(changeEvent) => {
                          const nextStartTime = changeEvent.target.value;

                          form.setValue("startTime", nextStartTime, {
                            shouldDirty: true,
                            shouldValidate: true,
                          });

                          const nextEndTime = endTimeThreeHoursAfter(nextStartTime);

                          if (nextEndTime) {
                            form.setValue("endTime", nextEndTime, {
                              shouldDirty: true,
                              shouldValidate: true,
                            });
                          }
                        }}
                      />

                      <FieldError message={form.formState.errors.startTime?.message} />
                    </div>

                    <div>
                      <label
                        htmlFor="event-end-time"
                        className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                      >
                        Heure de fin
                      </label>

                      <Input
                        id="event-end-time"
                        type="time"
                        className="w-full"
                        {...form.register("endTime")}
                      />

                      <FieldError message={form.formState.errors.endTime?.message} />
                    </div>
                  </div>

                  <div className="grid gap-5 md:grid-cols-2">
                    <div>
                      <label
                        htmlFor="event-capacity"
                        className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                      >
                        Capacité totale
                      </label>

                      <Input
                        id="event-capacity"
                        inputMode="numeric"
                        className="w-full"
                        placeholder="Ex. 45000"
                        {...form.register("capacityTotal")}
                      />

                      <FieldError message={form.formState.errors.capacityTotal?.message} />
                    </div>

                    <div>
                      <label
                        htmlFor="event-venue"
                        className="mb-2 block text-[13px] font-semibold text-[#33465c]"
                      >
                        Lieu
                      </label>

                      <Input
                        id="event-venue"
                        className="w-full"
                        placeholder="Ex. Stade Olympique"
                        {...form.register("venue")}
                      />

                      <FieldError message={form.formState.errors.venue?.message} />
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-[13px] font-semibold text-[#33465c]">
                      Image de l’événement
                    </p>

                    <label
                      htmlFor="event-image"
                      className="group block cursor-pointer rounded-2xl border-2 border-dashed border-[#d5dee7] bg-[#fbfcfd] p-5 transition hover:border-[#1769d2]/40 hover:bg-[#f8fbff]"
                    >
                      <input
                        id="event-image"
                        type="file"
                        accept="image/png,image/jpeg"
                        className="sr-only"
                        onChange={(event) => {
                          selectImage(event.target.files?.[0]);
                        }}
                      />

                      {imagePreview ? (
                        <div className="overflow-hidden rounded-xl border border-[#e0e6ec] bg-white">
                          <img
                            src={imagePreview}
                            alt="Aperçu de l’événement"
                            className="aspect-[2/1] w-full object-cover"
                          />

                          <div className="flex items-center justify-between gap-4 px-4 py-3">
                            <span className="truncate text-xs font-medium text-[#657386]">
                              {selectedImage?.name ?? "Image enregistrée"}
                            </span>

                            <span className="shrink-0 text-xs font-semibold text-[#1769d2]">
                              Remplacer
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="flex min-h-[150px] flex-col items-center justify-center text-center">
                          <span
                            aria-hidden="true"
                            className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-[#eaf2fd] text-[#1769d2]"
                          >
                            <svg
                              viewBox="0 0 24 24"
                              className="h-5 w-5"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="1.8"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <path d="M12 16V4" />
                              <path d="m7 9 5-5 5 5" />
                              <path d="M5 20h14" />
                            </svg>
                          </span>

                          <p className="text-sm font-semibold text-[#3e5065]">
                            Cliquez pour importer une image
                          </p>

                          <p className="mt-1 text-xs text-[#929dab]">PNG ou JPG · 5 Mo maximum</p>

                          <p className="mt-1 text-[11px] text-[#a7b0ba]">
                            Format recommandé : 1200 × 600 px
                          </p>
                        </div>
                      )}
                    </label>

                    {imageError ? (
                      <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
                        {imageError}
                      </p>
                    ) : null}
                  </div>

                  <div className="flex gap-3 rounded-xl border border-[#cfe2fb] bg-[#f3f8ff] px-4 py-4">
                    <span
                      aria-hidden="true"
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#1769d2] text-xs font-bold text-white"
                    >
                      i
                    </span>

                    <div>
                      <p className="text-sm font-semibold text-[#29455f]">Conseil</p>

                      <p className="mt-1 text-xs leading-5 text-[#678097]">
                        Utilisez un titre clair, une image lisible et vérifiez soigneusement la
                        date, les horaires et la capacité avant publication.
                      </p>
                    </div>
                  </div>

                  {apiError ? (
                    <div
                      role="alert"
                      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                    >
                      {apiError}
                    </div>
                  ) : null}

                  {successMessage ? (
                    <div
                      role="status"
                      className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800"
                    >
                      {successMessage}
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-col-reverse gap-3 border-t border-[#edf0f3] bg-[#fbfcfd] px-6 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-8">
                  <Link
                    to="/organizer"
                    className="inline-flex min-h-[44px] items-center justify-center rounded-xl px-4 text-sm font-semibold text-[#68788b] transition hover:bg-[#eef2f6] hover:text-[#30465d]"
                  >
                    Annuler
                  </Link>

                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      type="submit"
                      disabled={form.formState.isSubmitting}
                      className="border border-[#ccd6e0] bg-white px-5 font-semibold text-[#44586d] hover:bg-[#f7f9fb]"
                    >
                      {form.formState.isSubmitting
                        ? "Enregistrement…"
                        : savedEvent
                          ? "Mettre à jour le brouillon"
                          : "Enregistrer le brouillon"}
                    </Button>

                    <Button
                      type="button"
                      disabled={form.formState.isSubmitting}
                      onClick={() => {
                        void continueInformation();
                      }}
                      className="min-w-[220px] bg-[#1769d2] px-5 font-semibold shadow-[0_8px_20px_rgba(23,105,210,0.18)] hover:bg-[#125bb9]"
                    >
                      Continuer vers les catégories
                      <span aria-hidden="true" className="ml-2">
                        →
                      </span>
                    </Button>
                  </div>
                </div>
              </Card>
            </form>
          ) : step === 2 && savedEvent ? (
            <OrganizerEventCategoriesStep
              event={savedEvent}
              onBack={() => {
                setStep(1);
              }}
              onSaveDraft={() => {
                navigate(`/organizer/events/${savedEvent.id}`);
              }}
              onContinue={() => {
                setStep(3);
              }}
            />
          ) : step === 3 && savedEvent ? (
            <OrganizerEventPublicationStep
              event={savedEvent}
              onBack={() => {
                setStep(2);
              }}
              onPublished={() => {
                navigate("/organizer/events", {
                  replace: true,
                });
              }}
            />
          ) : null}
        </div>
      </main>
    </OrganizerShell>
  );
}
