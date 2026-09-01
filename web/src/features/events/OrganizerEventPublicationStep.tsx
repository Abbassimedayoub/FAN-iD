import {
  useState,
} from "react";
import {
  useQuery,
} from "@tanstack/react-query";
import {
  Link,
} from "react-router-dom";

import {
  Button,
  Card,
  Spinner,
} from "@/components/primitives";

import {
  fetchTicketCategories,
  publishEvent,
} from "./api";
import type {
  OrganizerEvent,
} from "./types";

interface OrganizerEventPublicationStepProps {
  event: OrganizerEvent;
  onBack: () => void;
  onPublished: (
    event: OrganizerEvent,
  ) => void;
}

function publicationErrorMessage(
  error: unknown,
): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "code" in error
  ) {
    const code = (
      error as {
        code?: unknown;
      }
    ).code;

    switch (code) {
      case "STALE_RESOURCE":
        return "Le brouillon a été modifié ailleurs. Rechargez les données avant de publier.";
      case "ORGANIZER_NOT_APPROVED":
        return "Votre organisation doit être approuvée avant de publier.";
      case "VALIDATION_ERROR":
        return "L’événement ne remplit pas encore toutes les conditions de publication.";
      case "CONFLICT":
        return "L’état actuel de l’événement ne permet pas sa publication.";
      case "NETWORK_ERROR":
        return "Connexion au serveur impossible. Réessayez.";
    }
  }

  return "Impossible de publier l’événement. Réessayez.";
}

function formatEventDate(
  value: string,
): string {
  const date = new Date(value);

  if (
    Number.isNaN(
      date.getTime(),
    )
  ) {
    return value;
  }

  return new Intl.DateTimeFormat(
    "fr-FR",
    {
      dateStyle: "long",
      timeStyle: "short",
    },
  ).format(date);
}

function ReadinessItem({
  ready,
  label,
  description,
}: {
  ready: boolean;
  label: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[#e4e9ef] bg-white px-4 py-4">
      <span
        aria-hidden="true"
        className={[
          "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold",
          ready
            ? "bg-emerald-100 text-emerald-700"
            : "bg-amber-100 text-amber-700",
        ].join(" ")}
      >
        {ready ? "✓" : "!"}
      </span>

      <div>
        <p className="text-sm font-semibold text-[#34485e]">
          {label}
        </p>

        <p className="mt-1 text-xs leading-5 text-[#82909f]">
          {description}
        </p>
      </div>
    </div>
  );
}

export function OrganizerEventPublicationStep({
  event,
  onBack,
  onPublished,
}: OrganizerEventPublicationStepProps) {
  const [
    pending,
    setPending,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );

  const categoriesQuery = useQuery({
    queryKey: [
      "catalog",
      "event",
      event.id,
      "ticket-categories",
    ],
    queryFn: () =>
      fetchTicketCategories(
        event.id,
      ),
  });

  const categories =
    categoriesQuery.data ?? [];

  const allocatedQuota =
    categories.reduce(
      (
        total,
        category,
      ) =>
        total +
        category.quota,
      0,
    );

  const venueReady =
    event.venue.trim().length > 0;

  const capacityTotal =
    event.capacity_total;

  const capacityReady =
    capacityTotal !== null &&
    capacityTotal > 0;

  const categoriesReady =
    categories.length > 0;

  const quotasReady =
    capacityTotal !== null &&
    capacityTotal > 0 &&
    allocatedQuota <=
      capacityTotal;

  const publicationReady =
    !categoriesQuery.isPending &&
    !categoriesQuery.isError &&
    venueReady &&
    capacityReady &&
    categoriesReady &&
    quotasReady;

  async function handlePublish(): Promise<void> {
    if (!publicationReady) {
      return;
    }

    setPending(true);
    setError(null);

    try {
      const published =
        await publishEvent(
          event,
        );

      onPublished(
        published,
      );
    } catch (caught) {
      setError(
        publicationErrorMessage(
          caught,
        ),
      );

      setPending(false);
    }
  }

  if (
    event.status === "PUBLISHED"
  ) {
    return (
      <Card className="overflow-hidden border-[#d8e8dc] p-0 shadow-[0_10px_28px_rgba(23,45,74,0.05)]">
        <div className="bg-emerald-50 px-6 py-8 text-center sm:px-8 sm:py-10">
          <span
            aria-hidden="true"
            className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-2xl font-bold text-emerald-700"
          >
            ✓
          </span>

          <h2 className="mt-5 font-sora text-2xl font-bold text-[#26384f]">
            Événement publié
          </h2>

          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[#64778a]">
            Votre événement est maintenant publié. Les informations structurelles et les catégories de billets sont verrouillées.
          </p>
        </div>

        <div className="grid gap-4 border-t border-[#e5ece7] bg-white px-6 py-6 sm:grid-cols-2 sm:px-8">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#929daa]">
              Événement
            </p>

            <p className="mt-2 font-semibold text-[#30445b]">
              {event.name}
            </p>
          </div>

          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#929daa]">
              Statut
            </p>

            <p className="mt-2 font-semibold text-emerald-700">
              Publié
            </p>
          </div>

          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#929daa]">
              Début
            </p>

            <p className="mt-2 text-sm font-semibold text-[#30445b]">
              {formatEventDate(
                event.starts_at,
              )}
            </p>
          </div>

          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#929daa]">
              Lieu
            </p>

            <p className="mt-2 text-sm font-semibold text-[#30445b]">
              {event.venue}
            </p>
          </div>
        </div>

        <div className="flex justify-center border-t border-[#edf0f3] bg-[#fbfcfd] px-6 py-5">
          <Link
            to="/organizer"
            className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-6 text-sm font-semibold text-white transition hover:bg-[#125bb9]"
          >
            Retour au tableau de bord
          </Link>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="overflow-hidden border-[#e1e7ed] p-0 shadow-[0_10px_28px_rgba(23,45,74,0.05)]">
        <div className="border-b border-[#edf0f3] px-6 py-5 sm:px-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="font-sora text-lg font-bold text-[#26384f]">
                Vérifier et publier
              </h2>

              <p className="mt-1 text-sm text-[#8591a0]">
                Contrôlez les informations avant de rendre l’événement disponible.
              </p>
            </div>

            <span className="rounded-full bg-amber-50 px-3 py-1.5 text-xs font-bold text-amber-700">
              Brouillon
            </span>
          </div>
        </div>

        <div className="grid gap-6 px-6 py-6 sm:px-8 lg:grid-cols-[220px_minmax(0,1fr)]">
          <div>
            {event.image_url ? (
              <img
                src={event.image_url}
                alt=""
                className="aspect-[2/1] w-full rounded-xl border border-[#e2e8ee] object-cover lg:aspect-[4/3]"
              />
            ) : (
              <div className="flex aspect-[4/3] items-center justify-center rounded-xl border border-dashed border-[#d8e0e8] bg-[#fafbfd] px-4 text-center">
                <p className="text-xs leading-5 text-[#929daa]">
                  Aucune image
                  <br />
                  L’image reste facultative.
                </p>
              </div>
            )}
          </div>

          <div>
            <h3 className="font-sora text-xl font-bold text-[#30445b]">
              {event.name}
            </h3>

            {event.description ? (
              <p className="mt-2 text-sm leading-6 text-[#6e7f90]">
                {event.description}
              </p>
            ) : null}

            <dl className="mt-5 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#9aa4af]">
                  Début
                </dt>

                <dd className="mt-1.5 text-sm font-semibold text-[#40556b]">
                  {formatEventDate(
                    event.starts_at,
                  )}
                </dd>
              </div>

              <div>
                <dt className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#9aa4af]">
                  Fin
                </dt>

                <dd className="mt-1.5 text-sm font-semibold text-[#40556b]">
                  {formatEventDate(
                    event.ends_at,
                  )}
                </dd>
              </div>

              <div>
                <dt className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#9aa4af]">
                  Lieu
                </dt>

                <dd className="mt-1.5 text-sm font-semibold text-[#40556b]">
                  {event.venue ||
                    "Non renseigné"}
                </dd>
              </div>

              <div>
                <dt className="text-[11px] font-bold uppercase tracking-[0.1em] text-[#9aa4af]">
                  Capacité
                </dt>

                <dd className="mt-1.5 text-sm font-semibold text-[#40556b]">
                  {event.capacity_total ??
                    "Non renseignée"}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </Card>

      <Card className="border-[#e1e7ed] p-6 shadow-[0_10px_28px_rgba(23,45,74,0.04)] sm:p-7">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h3 className="font-sora text-base font-bold text-[#30445b]">
              Vérifications avant publication
            </h3>

            <p className="mt-1 text-xs leading-5 text-[#8a96a4]">
              FANID vérifie les prérequis métier avant la publication.
            </p>
          </div>

          {publicationReady ? (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-700">
              Prêt à publier
            </span>
          ) : (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-700">
              À compléter
            </span>
          )}
        </div>

        {categoriesQuery.isPending ? (
          <div className="flex min-h-[120px] items-center justify-center">
            <Spinner label="Vérification des catégories" />
          </div>
        ) : categoriesQuery.isError ? (
          <div
            role="alert"
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700"
          >
            Impossible de vérifier les catégories de billets.
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            <ReadinessItem
              ready={venueReady}
              label="Lieu renseigné"
              description={
                venueReady
                  ? event.venue
                  : "Ajoutez le lieu de l’événement dans l’étape Informations."
              }
            />

            <ReadinessItem
              ready={capacityReady}
              label="Capacité définie"
              description={
                capacityReady
                  ? `${event.capacity_total} places au total.`
                  : "Définissez une capacité totale positive."
              }
            />

            <ReadinessItem
              ready={categoriesReady}
              label="Catégories de billets"
              description={
                categoriesReady
                  ? `${categories.length} catégorie${categories.length > 1 ? "s" : ""} configurée${categories.length > 1 ? "s" : ""}.`
                  : "Ajoutez au moins une catégorie de billets."
              }
            />

            <ReadinessItem
              ready={quotasReady}
              label="Quotas cohérents"
              description={
                capacityReady
                  ? `${allocatedQuota} place${allocatedQuota > 1 ? "s" : ""} allouée${allocatedQuota > 1 ? "s" : ""} sur ${event.capacity_total}.`
                  : "La capacité doit être définie avant de vérifier les quotas."
              }
            />
          </div>
        )}

        <div className="mt-5 rounded-xl border border-[#cfe2fb] bg-[#f3f8ff] px-4 py-4">
          <p className="text-sm font-semibold text-[#29455f]">
            Après publication
          </p>

          <p className="mt-1 text-xs leading-5 text-[#678097]">
            Les informations structurelles de l’événement et ses catégories de billets ne pourront plus être modifiées. Vérifiez-les soigneusement avant de continuer.
          </p>
        </div>

        {error ? (
          <div
            role="alert"
            className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        ) : null}
      </Card>

      <div className="flex flex-col-reverse gap-3 border-t border-[#e4e9ee] pt-5 sm:flex-row sm:items-center sm:justify-between">
        <Button
          type="button"
          disabled={pending}
          onClick={onBack}
          className="border border-[#ccd6e0] bg-white px-5 font-semibold text-[#536578] hover:bg-[#f7f9fb]"
        >
          ← Retour aux catégories
        </Button>

        <Button
          type="button"
          disabled={
            pending ||
            !publicationReady
          }
          onClick={() => {
            void handlePublish();
          }}
          className="min-w-[210px] bg-[#1769d2] px-6 font-semibold shadow-[0_8px_20px_rgba(23,105,210,0.18)] hover:bg-[#125bb9]"
        >
          {pending
            ? "Publication…"
            : "Publier l’événement"}
        </Button>
      </div>
    </div>
  );
}
