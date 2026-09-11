import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import { BrandMark } from "@/components/BrandMark";
import { Badge, Button, Card } from "@/components/primitives";

import { fetchMyCommissionNegotiation, organizerCommissionQueryKeys } from "./commission";
import { fetchMyOrganizer, myOrganizerQueryKey } from "./myOrganizer";
import { OrganizerCommissionPanel } from "./OrganizerCommissionPanel";
import { OrganizerShell } from "./OrganizerShell";
import {
  fetchMyOrganizerReactivationRequest,
  myOrganizerReactivationQueryKey,
  requestMyOrganizerReactivation,
} from "./reactivationHome";
import type { OrganizerStatus } from "./types";

const STATUS_CONTENT: Record<
  OrganizerStatus,
  {
    title: string;
    description: string;
    badge: string;
  }
> = {
  PENDING: {
    title: "Demande en cours d’examen",
    description:
      "Votre compte organisateur a bien été créé. Votre dossier est maintenant en attente de validation par un administrateur FANID.",
    badge: "En attente",
  },
  APPROVED: {
    title: "Compte organisateur validé",
    description: "Votre dossier a été approuvé. Votre espace organisateur est actif.",
    badge: "Approuvé",
  },
  REJECTED: {
    title: "Demande non approuvée",
    description: "Votre dossier a été examiné mais n’a pas été approuvé.",
    badge: "Rejeté",
  },
  SUSPENDED: {
    title: "Compte organisateur suspendu",
    description: "L’accès opérationnel de votre organisation est actuellement suspendu.",
    badge: "Suspendu",
  },
};

export function OrganizerHomePage() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: myOrganizerQueryKey,
    queryFn: fetchMyOrganizer,
  });

  const commissionQuery = useQuery({
    queryKey: organizerCommissionQueryKeys.my,
    queryFn: fetchMyCommissionNegotiation,
    enabled: Boolean(query.data) && query.data?.validation_status !== "SUSPENDED",
    retry: false,
  });

  const reactivationQuery = useQuery({
    queryKey: myOrganizerReactivationQueryKey,
    queryFn: fetchMyOrganizerReactivationRequest,
    enabled: query.data?.validation_status === "SUSPENDED",
    retry: false,
  });

  const reactivationMutation = useMutation({
    mutationFn: requestMyOrganizerReactivation,
    onSuccess: (reactivationRequest) => {
      queryClient.setQueryData(myOrganizerReactivationQueryKey, {
        request: reactivationRequest,
      });
    },
  });

  if (query.isPending) {
    return (
      <OrganizerShell activeItem="overview">
        <main className="flex min-h-[calc(100vh-78px)] items-center justify-center p-6">
          <p role="status" className="text-sm text-navy/60">
            Chargement de votre espace organisateur…
          </p>
        </main>
      </OrganizerShell>
    );
  }

  if (query.isError || !query.data) {
    return (
      <OrganizerShell activeItem="overview">
        <main className="flex min-h-[calc(100vh-78px)] items-center justify-center p-6">
          <Card className="w-full max-w-lg p-8 text-center">
            <BrandMark compact className="mx-auto mb-6 text-navy" />

            <h1 className="font-sora text-2xl font-bold text-navy">
              Espace organisateur indisponible
            </h1>

            <p className="mt-3 text-sm leading-6 text-navy/60">
              Impossible de charger votre dossier pour le moment. Réessayez dans quelques instants.
            </p>
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  const organizer = query.data;
  const content = STATUS_CONTENT[organizer.validation_status];
  const approved = organizer.validation_status === "APPROVED";
  const commissionAgreed = commissionQuery.data?.commission_status === "COMMISSION_AGREED";
  const commerciallyReady = approved && commissionAgreed;

  const reactivationRequest = reactivationQuery.data?.request ?? null;

  const reactivationPending = reactivationRequest?.status === "PENDING";

  const existingOrganizerNotice =
    (
      location.state as {
        existingOrganizerAccount?: boolean;
      } | null
    )?.existingOrganizerAccount === true;

  return (
    <OrganizerShell
      activeItem="overview"
      eventsAvailable={commerciallyReady}
      breadcrumbs={
        <>
          <span>Accueil</span>
          <span aria-hidden="true">/</span>
          <span className="text-navy/70">Vue d’ensemble</span>
        </>
      }
    >
      <main className="fanid-page px-5 py-8 sm:px-8">
        <div className="mx-auto max-w-[1240px]">
          <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="fanid-eyebrow">Espace organisateur</p>
              <h1 className="fanid-page-title mt-2">Vue d’ensemble</h1>
              <p className="fanid-page-description">
                Suivez le statut de votre organisation et accédez à vos outils.
              </p>
            </div>
            <Badge>{content.badge}</Badge>
          </header>

          {existingOrganizerNotice ? (
            <Card className="mb-6 border-primary/20 bg-primary/5 p-5">
              <p className="text-sm font-semibold text-navy">Ce compte organisateur existe déjà.</p>

              <p className="mt-2 text-sm leading-6 text-navy/60">
                {organizer.validation_status === "SUSPENDED"
                  ? "Ce compte est suspendu. Demandez sa réouverture : seul un administrateur FANID pourra l’accepter avec sa vérification OTP."
                  : "Vous avez été redirigé vers l’espace organisateur déjà associé à cette adresse e-mail."}
              </p>
            </Card>
          ) : null}

          {organizer.validation_status !== "SUSPENDED" ? (
            <OrganizerCommissionPanel
              organizer={organizer}
              negotiation={commissionQuery.data}
              isPending={commissionQuery.isPending}
              isError={commissionQuery.isError}
              onRetry={() => {
                void commissionQuery.refetch();
              }}
            />
          ) : null}

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
            <Card className="overflow-hidden border-white/80 p-0 shadow-[0_24px_70px_rgba(14,42,77,0.10)]">
              <div className="border-b border-navy/10 bg-white p-7 sm:p-9">
                <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-primary">
                  Espace organisateur
                </p>

                <h1 className="font-sora text-3xl font-bold tracking-[-0.03em] text-navy">
                  {content.title}
                </h1>

                <p className="mt-4 max-w-2xl text-sm leading-7 text-navy/60">
                  {content.description}
                </p>

                {organizer.validation_status === "SUSPENDED" ? (
                  <div className="mt-6 rounded-2xl border border-primary/20 bg-primary/5 p-5">
                    <p className="text-sm font-semibold text-navy">
                      Réouverture soumise à validation administrateur
                    </p>

                    <p className="mt-2 text-sm leading-6 text-navy/65">
                      Votre compte reste suspendu jusqu’à la décision d’un administrateur FANID.
                      Vous ne pouvez pas le réactiver vous-même.
                    </p>

                    {reactivationQuery.isPending ? (
                      <p role="status" className="mt-4 text-sm text-navy/55">
                        Vérification de votre demande de réouverture…
                      </p>
                    ) : null}

                    {reactivationPending ? (
                      <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
                        <p className="text-sm font-semibold text-amber-900">
                          Demande de réouverture en attente de validation administrateur.
                        </p>

                        <p className="mt-2 text-sm leading-6 text-amber-800">
                          Un administrateur doit accepter cette demande avec sa vérification OTP.
                          Vous recevrez un e-mail lorsque la décision sera prise.
                        </p>
                      </div>
                    ) : (
                      <>
                        {reactivationRequest?.status === "REJECTED" ? (
                          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4">
                            <p className="text-sm font-semibold text-red-800">
                              La précédente demande de réouverture a été refusée.
                            </p>

                            {reactivationRequest.rejection_reason ? (
                              <p className="mt-2 text-sm text-red-700">
                                Motif : {reactivationRequest.rejection_reason}
                              </p>
                            ) : null}
                          </div>
                        ) : null}

                        <Button
                          type="button"
                          className="mt-4"
                          disabled={reactivationMutation.isPending || reactivationQuery.isPending}
                          onClick={() => {
                            reactivationMutation.mutate();
                          }}
                        >
                          {reactivationMutation.isPending
                            ? "Envoi de la demande…"
                            : "Demander la réouverture"}
                        </Button>
                      </>
                    )}

                    {reactivationMutation.isError || reactivationQuery.isError ? (
                      <p role="alert" className="mt-3 text-sm text-red-700">
                        Impossible de traiter la demande de réouverture. Réessayez.
                      </p>
                    ) : null}
                  </div>
                ) : null}

                {organizer.validation_status === "REJECTED" && organizer.rejection_reason ? (
                  <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4">
                    <p className="text-xs font-bold uppercase tracking-[0.1em] text-red-700">
                      Motif
                    </p>

                    <p className="mt-2 text-sm leading-6 text-red-800">
                      {organizer.rejection_reason}
                    </p>
                  </div>
                ) : null}
              </div>

              <div className="grid gap-4 bg-[#fbfcfe] p-7 sm:grid-cols-2 sm:p-9">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-navy/40">
                    Organisation
                  </p>
                  <p className="mt-2 font-semibold text-navy">{organizer.org_name}</p>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-navy/40">
                    E-mail de contact
                  </p>
                  <p className="mt-2 break-all font-semibold text-navy">
                    {organizer.contact_email}
                  </p>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-navy/40">
                    Numéro de TVA
                  </p>
                  <p className="mt-2 font-semibold text-navy">
                    {organizer.vat_number || "Non renseigné"}
                  </p>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.1em] text-navy/40">
                    Statut du dossier
                  </p>
                  <p className="mt-2 font-semibold text-navy">{content.badge}</p>
                </div>
              </div>
            </Card>

            <div className="space-y-5">
              <Card className="p-6">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">
                  Événements
                </p>

                <h2 className="mt-3 font-sora text-xl font-bold text-navy">
                  Gestion événementielle
                </h2>

                {commerciallyReady ? (
                  <>
                    <p className="mt-3 text-sm leading-6 text-navy/55">
                      Le compte et la commission sont validés. La gestion événementielle est active.
                    </p>

                    <Link
                      to="/organizer/events/new"
                      className="mt-5 inline-flex min-h-[46px] w-full items-center justify-center rounded-xl bg-primary px-4 text-sm font-semibold text-white transition hover:bg-primary/90"
                    >
                      Créer un événement
                    </Link>
                  </>
                ) : (
                  <p className="mt-3 text-sm leading-6 text-navy/55">
                    {!approved
                      ? "La gestion des événements nécessite d’abord l’approbation du compte organisateur."
                      : "Votre compte est approuvé, mais un accord de commission avec FANID est requis avant de créer ou gérer des événements."}
                  </p>
                )}
              </Card>

              <Card className="border-primary/15 bg-[#f8fbff] p-6">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">Compte</p>

                <h2 className="mt-3 font-sora text-xl font-bold text-navy">Mes sessions</h2>

                <p className="mt-2 text-sm leading-6 text-navy/55">
                  Consultez vos appareils connectés et révoquez ceux que vous ne reconnaissez pas.
                </p>

                <Link
                  to="/sessions"
                  className="mt-5 inline-flex min-h-[46px] w-full items-center justify-center rounded-xl bg-primary px-4 text-sm font-semibold text-white transition hover:bg-[#1256ac]"
                >
                  Gérer mes sessions
                </Link>
              </Card>

              <Card className="p-6">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-navy/40">
                  Sécurité du compte
                </p>

                <div className="mt-4">
                  <Link
                    to="/organizer/security"
                    className="flex min-h-[46px] items-center justify-between rounded-xl border border-primary bg-white px-4 text-sm font-semibold text-primary transition hover:bg-[#eef5ff]"
                  >
                    <span>Changer le mot de passe</span>
                    <span aria-hidden="true">→</span>
                  </Link>
                </div>
              </Card>
            </div>
          </div>
        </div>
      </main>
    </OrganizerShell>
  );
}
