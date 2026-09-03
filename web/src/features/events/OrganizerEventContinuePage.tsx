import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Card, Spinner } from "@/components/primitives";
import { OrganizerShell } from "@/features/organizers/OrganizerShell";

import { fetchOrganizerEvent } from "./api";
import { OrganizerEventCategoriesStep } from "./OrganizerEventCategoriesStep";
import { OrganizerEventPublicationStep } from "./OrganizerEventPublicationStep";
import type { OrganizerEvent } from "./types";

function DraftContinuation({ event }: { event: OrganizerEvent }) {
  const navigate = useNavigate();

  const current = event;

  const [step, setStep] = useState<2 | 3>(2);

  return (
    <>
      <div className="mb-6 rounded-2xl border border-[#e1e7ed] bg-white px-5 py-5 shadow-sm sm:px-7">
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={[
              "flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold",
              step === 2 ? "bg-[#1769d2] text-white" : "bg-emerald-100 text-emerald-700",
            ].join(" ")}
          >
            {step === 2 ? "2" : "✓"}
          </span>

          <span className="text-sm font-semibold text-[#30445b]">Catégories & quotas</span>

          <span aria-hidden="true" className="hidden h-px flex-1 bg-[#dfe5eb] sm:block" />

          <span
            className={[
              "flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold",
              step === 3
                ? "bg-[#1769d2] text-white"
                : "border border-[#d8e0e8] bg-white text-[#8492a3]",
            ].join(" ")}
          >
            3
          </span>

          <span
            className={[
              "text-sm font-semibold",
              step === 3 ? "text-[#30445b]" : "text-[#8c98a7]",
            ].join(" ")}
          >
            Publication
          </span>
        </div>
      </div>

      {step === 2 ? (
        <OrganizerEventCategoriesStep
          event={current}
          onBack={() => {
            navigate(`/organizer/events/${current.id}/edit`);
          }}
          onSaveDraft={() => {
            navigate(`/organizer/events/${current.id}`);
          }}
          onContinue={() => {
            setStep(3);
          }}
        />
      ) : (
        <OrganizerEventPublicationStep
          event={current}
          onBack={() => {
            setStep(2);
          }}
          onPublished={() => {
            navigate("/organizer/events", {
              replace: true,
            });
          }}
        />
      )}
    </>
  );
}

export function OrganizerEventContinuePage() {
  const { eventId } = useParams<{
    eventId: string;
  }>();

  const query = useQuery({
    queryKey: ["catalog", "event", eventId, "continue"],
    queryFn: () => {
      if (!eventId) {
        throw new Error("EVENT_ID_REQUIRED");
      }

      return fetchOrganizerEvent(eventId);
    },
    enabled: Boolean(eventId),
  });

  const breadcrumbs = (
    <div className="flex items-center gap-2 text-sm">
      <Link to="/organizer/events" className="font-medium text-[#8a96a5] hover:text-[#1769d2]">
        Événements
      </Link>

      <span aria-hidden="true" className="text-[#b4bdc8]">
        /
      </span>

      <span className="font-semibold text-[#34465c]">Continuer la création</span>
    </div>
  );

  return (
    <OrganizerShell activeItem="events" breadcrumbs={breadcrumbs}>
      <main className="px-5 py-7 sm:px-8 lg:px-10 lg:py-9">
        <div className="mx-auto max-w-[1060px]">
          <div className="mb-7">
            <h1 className="font-sora text-[28px] font-bold tracking-[-0.025em] text-[#26384f]">
              Continuer la création
            </h1>

            <p className="mt-2 text-sm text-[#778596]">
              Reprenez votre brouillon, complétez les catégories puis publiez uniquement lorsque
              tout est prêt.
            </p>
          </div>

          {query.isPending ? (
            <div className="flex min-h-[420px] items-center justify-center">
              <Spinner label="Chargement du brouillon" />
            </div>
          ) : query.isError || !query.data ? (
            <Card className="p-8 text-center">
              <h2 className="font-sora text-xl font-bold text-[#30445b]">Brouillon introuvable</h2>

              <Link
                to="/organizer/events"
                className="mt-5 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
              >
                Retour aux événements
              </Link>
            </Card>
          ) : query.data.status !== "DRAFT" ? (
            <Card className="p-8 text-center">
              <h2 className="font-sora text-xl font-bold text-[#30445b]">
                Cet événement n’est plus un brouillon
              </h2>

              <p className="mt-3 text-sm text-[#718195]">
                Seuls les événements en brouillon peuvent reprendre le parcours de création.
              </p>

              <Link
                to={`/organizer/events/${query.data.id}`}
                className="mt-5 inline-flex min-h-[44px] items-center justify-center rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white"
              >
                Voir l’événement
              </Link>
            </Card>
          ) : (
            <DraftContinuation event={query.data} />
          )}
        </div>
      </main>
    </OrganizerShell>
  );
}
