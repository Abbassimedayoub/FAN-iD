import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, Card, Input, Spinner } from "@/components/primitives";
import { toAppError } from "@/lib/errors";

import { fetchMyOrganizer, myOrganizerQueryKey } from "./myOrganizer";
import { OrganizerShell } from "./OrganizerShell";
import {
  fetchOrganizerArchivedScannersPage,
  inviteOrganizerScanner,
  organizerArchivedScannersQueryKey,
  organizerScannersQueryKey,
  type OrganizerScanner,
  type ScannerStatus,
} from "./scanners";

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function statusLabel(scanner: OrganizerScanner): string {
  if (scanner.status === "INVITATION_CANCELLED") {
    return "Invitation annulée";
  }

  if (scanner.status === "DELETED") {
    return "Compte retiré";
  }

  return scanner.status;
}

function initials(scanner: OrganizerScanner): string {
  return (
    [scanner.first_name, scanner.last_name]
      .filter(Boolean)
      .map((value) => value[0]?.toUpperCase())
      .join("")
      .slice(0, 2) || "SC"
  );
}

export function OrganizerArchivedScannersPage() {
  const queryClient = useQueryClient();
  const [reinviteMessage, setReinviteMessage] = useState<string | null>(null);

  const [archivePage, setArchivePage] = useState(1);
  const [archiveSearch, setArchiveSearch] = useState("");
  const [archiveStatus, setArchiveStatus] = useState<
    Extract<ScannerStatus, "INVITATION_CANCELLED" | "DELETED"> | ""
  >("");

  const reinviteMutation = useMutation({
    mutationFn: (scanner: OrganizerScanner) =>
      inviteOrganizerScanner({
        first_name: scanner.first_name,
        last_name: scanner.last_name,
        email: scanner.email,
      }),

    onSuccess: async (created) => {
      setReinviteMessage(
        `Nouvelle invitation envoyée à ${created.first_name} ${created.last_name}. ` +
          "Un nouveau compte scanner a été créé avec un mot de passe temporaire valable 5 minutes.",
      );

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  const organizerQuery = useQuery({
    queryKey: myOrganizerQueryKey,
    queryFn: fetchMyOrganizer,
  });

  const approved = organizerQuery.data?.validation_status === "APPROVED";

  const archivesQuery = useQuery({
    queryKey: [
      ...organizerArchivedScannersQueryKey,
      {
        page: archivePage,
        search: archiveSearch.trim(),
        status: archiveStatus,
      },
    ],
    queryFn: () =>
      fetchOrganizerArchivedScannersPage({
        page: archivePage,
        search: archiveSearch,
        status: archiveStatus || undefined,
      }),
    enabled: approved,
  });

  const breadcrumbs = (
    <div className="flex items-center gap-2 text-sm font-semibold text-[#34465c]">
      <Link to="/organizer/scanners" className="text-[#1769d2] hover:underline">
        Scanners
      </Link>
      <span className="text-[#9aa6b4]">/</span>
      <span>Archives</span>
    </div>
  );

  if (organizerQuery.isPending) {
    return (
      <OrganizerShell activeItem="scanners" breadcrumbs={breadcrumbs}>
        <div className="flex min-h-[520px] items-center justify-center">
          <Spinner label="Chargement des archives scanners" />
        </div>
      </OrganizerShell>
    );
  }

  if (organizerQuery.isError || !organizerQuery.data) {
    return (
      <OrganizerShell activeItem="scanners" breadcrumbs={breadcrumbs}>
        <main className="p-6 lg:p-10">
          <Card className="mx-auto max-w-xl p-8 text-center">
            Impossible de charger votre espace organisateur.
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  if (!approved) {
    return (
      <OrganizerShell activeItem="scanners" breadcrumbs={breadcrumbs}>
        <main className="p-6 lg:p-10">
          <Card className="mx-auto max-w-xl p-8 text-center">
            Votre compte organisateur doit être approuvé avant de consulter les archives.
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  const archivePageData = archivesQuery.data;
  const scanners = archivePageData?.results ?? [];
  const archiveCount = archivePageData?.count ?? 0;
  const archiveTotalPages = Math.max(
    1,
    Math.ceil(archiveCount / 5),
  );

  return (
    <OrganizerShell activeItem="scanners" breadcrumbs={breadcrumbs}>
      <main className="p-5 sm:p-7 lg:p-10">
        <div className="mx-auto max-w-[1180px]">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#1769d2]">
                Historique
              </p>

              <h1 className="mt-2 font-sora text-3xl font-bold tracking-[-0.03em] text-[#25394f]">
                Scanners archivés
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#718195]">
                Retrouvez ici les anciens scanners retirés de votre équipe. Leur accès reste
                désactivé.
              </p>
            </div>

            <Link to="/organizer/scanners">
              <Button type="button">Retour à l’équipe scanner</Button>
            </Link>
          </div>

          {reinviteMessage ? (
            <div
              role="status"
              className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
            >
              {reinviteMessage}
            </div>
          ) : null}

          {reinviteMutation.isError ? (
            <div
              role="alert"
              className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {toAppError(reinviteMutation.error).message}
            </div>
          ) : null}

          <div className="mt-8">
            <Card className="mb-4 border-[#dfe6ed] p-4">
              <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_260px]">
                <label htmlFor="archive-scanner-search" className="block">
                  <span className="mb-2 block text-sm font-semibold text-[#40546a]">
                    Rechercher
                  </span>

                  <Input
                    id="archive-scanner-search"
                    type="search"
                    value={archiveSearch}
                    placeholder="Nom, prénom ou e-mail"
                    onChange={(event) => {
                      setArchiveSearch(event.target.value);
                      setArchivePage(1);
                    }}
                    className="w-full"
                  />
                </label>

                <label htmlFor="archive-scanner-status" className="block">
                  <span className="mb-2 block text-sm font-semibold text-[#40546a]">
                    État
                  </span>

                  <select
                    id="archive-scanner-status"
                    value={archiveStatus}
                    onChange={(event) => {
                      setArchiveStatus(
                        event.target.value as
                          | "INVITATION_CANCELLED"
                          | "DELETED"
                          | "",
                      );
                      setArchivePage(1);
                    }}
                    className="min-h-[44px] w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-2.5 text-navy shadow-sm outline-none transition hover:border-navy/25 focus:border-cyan focus:ring-4 focus:ring-cyan/10"
                  >
                    <option value="">Tous les états</option>
                    <option value="INVITATION_CANCELLED">
                      Invitation annulée
                    </option>
                    <option value="DELETED">
                      Compte retiré
                    </option>
                  </select>
                </label>
              </div>
            </Card>

            {archivesQuery.isPending ? (
              <Card className="flex min-h-[300px] items-center justify-center">
                <Spinner label="Chargement des scanners archivés" />
              </Card>
            ) : null}

            {archivesQuery.isError ? (
              <Card className="p-8 text-center">
                <p role="alert" className="text-sm text-red-700">
                  {toAppError(archivesQuery.error).message}
                </p>

                <Button
                  type="button"
                  className="mt-4"
                  onClick={() => {
                    void archivesQuery.refetch();
                  }}
                >
                  Réessayer
                </Button>
              </Card>
            ) : null}

            {!archivesQuery.isPending && !archivesQuery.isError && scanners.length === 0 ? (
              <Card className="p-10 text-center">
                <h2 className="font-sora text-lg font-bold text-[#293c52]">
                  {archiveSearch.trim() || archiveStatus
                    ? "Aucune archive correspondante"
                    : "Aucun scanner archivé"}
                </h2>

                <p className="mt-2 text-sm text-[#718195]">
                  {archiveSearch.trim() || archiveStatus
                    ? "Modifiez la recherche ou l’état sélectionné."
                    : "Les scanners que vous retirez de la liste apparaîtront ici."}
                </p>
              </Card>
            ) : null}

            {!archivesQuery.isError && scanners.length > 0 ? (
              <div className="space-y-4">
                <div className="text-sm font-semibold text-[#718195]">
                  {archiveCount} {archiveCount > 1 ? "archives" : "archive"}
                </div>

                {scanners.map((scanner) => (
                  <Card
                    key={scanner.id}
                    className="border-[#e0e7ee] p-5 shadow-[0_10px_28px_rgba(23,45,74,0.05)]"
                  >
                    <div className="flex items-start gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-sm font-bold text-slate-600">
                        {initials(scanner)}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h2 className="truncate font-sora text-base font-bold text-[#293c52]">
                              {scanner.first_name} {scanner.last_name}
                            </h2>

                            <p className="mt-1 truncate text-sm text-[#738295]">{scanner.email}</p>

                            <p className="mt-1 text-sm text-[#738295]">
                              Téléphone :{" "}
                              <span className="font-semibold text-[#516477]">
                                {scanner.phone?.trim() || "Non renseigné"}
                              </span>
                            </p>
                          </div>

                          <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 ring-1 ring-inset ring-slate-200">
                            {statusLabel(scanner)}
                          </span>
                        </div>

                        <dl className="mt-5 grid gap-4 border-t border-[#edf0f3] pt-4 text-xs sm:grid-cols-3">
                          <div>
                            <dt className="text-[#9aa6b4]">Invitation créée</dt>
                            <dd className="mt-1 font-semibold text-[#536579]">
                              {formatDate(scanner.created_at)}
                            </dd>
                          </div>

                          <div>
                            <dt className="text-[#9aa6b4]">Retrait de l’équipe</dt>
                            <dd className="mt-1 font-semibold text-[#536579]">
                              {formatDate(scanner.removed_at)}
                            </dd>
                          </div>

                          <div>
                            <dt className="text-[#9aa6b4]">Archivage</dt>
                            <dd className="mt-1 font-semibold text-[#536579]">
                              {formatDate(scanner.archived_at)}
                            </dd>
                          </div>
                        </dl>

                        <p className="mt-4 text-xs leading-5 text-[#8995a3]">
                          Cette ancienne entrée reste conservée pour la traçabilité. Une
                          réinvitation crée un nouveau compte scanner sécurisé : l’ancien compte
                          supprimé n’est jamais réactivé.
                        </p>

                        <Button
                          type="button"
                          className="mt-4"
                          disabled={
                            reinviteMutation.isPending &&
                            reinviteMutation.variables?.id === scanner.id
                          }
                          onClick={() => {
                            setReinviteMessage(null);
                            reinviteMutation.reset();
                            reinviteMutation.mutate(scanner);
                          }}
                        >
                          {reinviteMutation.isPending &&
                          reinviteMutation.variables?.id === scanner.id
                            ? "Envoi…"
                            : "Réinviter ce scanner"}
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}

                <div className="flex flex-col gap-3 rounded-xl border border-[#dfe6ed] bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm font-medium text-[#617286]">
                    Page {archivePage} sur {archiveTotalPages}
                  </p>

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      disabled={
                        archivePage <= 1 ||
                        archivePageData?.previous == null ||
                        archivesQuery.isFetching
                      }
                      onClick={() => {
                        setArchivePage((current) =>
                          Math.max(1, current - 1),
                        );
                      }}
                      className="border border-[#d7e0e9] bg-white font-semibold text-[#40546a] hover:bg-slate-50"
                    >
                      Précédent
                    </Button>

                    <Button
                      type="button"
                      disabled={
                        archivePage >= archiveTotalPages ||
                        archivePageData?.next == null ||
                        archivesQuery.isFetching
                      }
                      onClick={() => {
                        setArchivePage((current) =>
                          Math.min(
                            archiveTotalPages,
                            current + 1,
                          ),
                        );
                      }}
                      className="bg-[#1769d2] font-semibold text-white"
                    >
                      Suivant
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </main>
    </OrganizerShell>
  );
}
