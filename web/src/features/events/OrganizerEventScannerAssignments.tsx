import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Card, Spinner } from "@/components/primitives";
import {
  fetchOrganizerScanners,
  organizerScannersQueryKey,
  type OrganizerScanner,
  type ScannerStatus,
} from "@/features/organizers/scanners";

import { assignEventScanner, fetchEventScannerAssignments, unassignEventScanner } from "./api";
import type { EventScannerAssignment, OrganizerEvent } from "./types";

const ASSIGNABLE_SCANNER_STATUSES = new Set<ScannerStatus>([
  "INVITED",
  "EMAIL_SENT",
  "OPENED",
  "ACTIVE",
]);

const SCANNER_STATUS_LABELS: Record<ScannerStatus, string> = {
  INVITED: "Invitation créée",
  EMAIL_SENT: "Invitation envoyée",
  OPENED: "Compte ouvert",
  ACTIVE: "Compte actif",
  LEAVE_REQUESTED: "Départ demandé",
  INVITATION_CANCELLED: "Invitation annulée",
  DELETED: "Compte supprimé",
};

function scannerName(scanner: { first_name: string; last_name: string }): string {
  return [scanner.first_name, scanner.last_name].filter(Boolean).join(" ").trim();
}

export function isAssignableScanner(scanner: OrganizerScanner): boolean {
  return scanner.archived_at === null && ASSIGNABLE_SCANNER_STATUSES.has(scanner.status);
}

export function isCurrentAssignment(assignment: { status: ScannerStatus }): boolean {
  return assignment.status !== "INVITATION_CANCELLED" && assignment.status !== "DELETED";
}

interface OrganizerEventScannerAssignmentsProps {
  event: OrganizerEvent;
}

export function OrganizerEventScannerAssignments({ event }: OrganizerEventScannerAssignmentsProps) {
  const queryClient = useQueryClient();

  const draft = event.status === "DRAFT";

  const canAssign = event.status === "PUBLISHED" || event.status === "POSTPONED";

  const assignmentQueryKey = ["catalog", "event", event.id, "scanners"] as const;

  const assignmentsQuery = useQuery({
    queryKey: assignmentQueryKey,
    queryFn: () => fetchEventScannerAssignments(event.id),
    enabled: !draft,
  });

  const scannersQuery = useQuery({
    queryKey: organizerScannersQueryKey,
    queryFn: fetchOrganizerScanners,
    enabled: canAssign,
  });

  const assignMutation = useMutation({
    mutationFn: (scannerId: string) => assignEventScanner(event.id, scannerId),

    onSuccess: (assignment) => {
      queryClient.setQueryData<EventScannerAssignment[]>(assignmentQueryKey, (current = []) => {
        if (current.some((item) => item.scanner_id === assignment.scanner_id)) {
          return current;
        }

        return [...current, assignment];
      });
    },
  });

  const unassignMutation = useMutation({
    mutationFn: (scannerId: string) => unassignEventScanner(event.id, scannerId),

    onSuccess: (_data, scannerId) => {
      queryClient.setQueryData<EventScannerAssignment[]>(assignmentQueryKey, (current = []) =>
        current.filter((assignment) => assignment.scanner_id !== scannerId),
      );
    },
  });

  if (draft) {
    return (
      <Card className="p-6 sm:p-8">
        <h2 className="font-sora text-lg font-bold text-[#30445b]">Affectation des scanners</h2>

        <div className="mt-5 rounded-2xl border border-[#dbe5ef] bg-[#f7fafc] p-5">
          <p className="font-semibold text-[#40556b]">Affectation disponible après publication</p>

          <p className="mt-2 text-sm leading-6 text-[#718195]">
            Publiez l’événement avant d’affecter des scanners. Les scanners ne peuvent pas être
            affectés à un brouillon.
          </p>
        </div>
      </Card>
    );
  }

  const assignments = (assignmentsQuery.data ?? []).filter(isCurrentAssignment);

  const assignedScannerIds = new Set(assignments.map((assignment) => assignment.scanner_id));

  const organizerScanners = scannersQuery.data ?? [];
  const assignableScanners = organizerScanners.filter(isAssignableScanner);

  const availableScanners = assignableScanners.filter(
    (scanner) => !assignedScannerIds.has(scanner.id),
  );

  const noScannerAvailable =
    canAssign &&
    scannersQuery.isSuccess &&
    assignableScanners.length === 0 &&
    (assignmentsQuery.isError || (assignmentsQuery.isSuccess && assignments.length === 0));

  const mutationError = assignMutation.isError || unassignMutation.isError;

  return (
    <Card className="p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-sora text-lg font-bold text-[#30445b]">Affectation des scanners</h2>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#7a8999]">
            Un événement peut avoir plusieurs scanners et un même scanner peut être affecté à
            plusieurs événements du même organisateur.
          </p>
        </div>

        <span className="rounded-full bg-[#edf5ff] px-3 py-1 text-xs font-bold text-[#1769d2]">
          {assignments.length} affecté
          {assignments.length > 1 ? "s" : ""}
        </span>
      </div>

      {mutationError ? (
        <p
          role="alert"
          className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
        >
          L’opération n’a pas pu être effectuée. Réessayez.
        </p>
      ) : null}

      {assignmentsQuery.isPending ? (
        <div className="mt-6">
          <Spinner label="Chargement des scanners affectés" />
        </div>
      ) : assignmentsQuery.isError && !noScannerAvailable ? (
        <p role="alert" className="mt-5 text-sm font-medium text-red-700">
          Impossible de charger les scanners affectés.
        </p>
      ) : (
        <>
          <div className="mt-7">
            <h3 className="text-sm font-bold text-[#40556b]">Scanners affectés</h3>

            {assignments.length > 0 ? (
              <div className="mt-3 divide-y divide-[#edf0f3] rounded-2xl border border-[#e3e9ef]">
                {assignments.map((assignment) => {
                  const name = scannerName(assignment);

                  const removing =
                    unassignMutation.isPending &&
                    unassignMutation.variables === assignment.scanner_id;

                  return (
                    <div
                      key={assignment.assignment_id}
                      className="flex flex-wrap items-center justify-between gap-4 p-4"
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-[#40556b]">{name || assignment.email}</p>

                        <p className="mt-1 break-all text-xs text-[#8492a2]">{assignment.email}</p>

                        <p className="mt-1 text-xs font-semibold text-[#6b7d91]">
                          {SCANNER_STATUS_LABELS[assignment.status]}
                        </p>
                      </div>

                      <Button
                        type="button"
                        className="bg-navy"
                        disabled={unassignMutation.isPending || assignMutation.isPending}
                        aria-label={`Retirer ${name || assignment.email}`}
                        onClick={() => {
                          unassignMutation.mutate(assignment.scanner_id);
                        }}
                      >
                        {removing ? "Retrait…" : "Retirer"}
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 rounded-2xl border border-dashed border-[#d7e0e9] px-4 py-5 text-sm text-[#7d8c9c]">
                Aucun scanner affecté
              </p>
            )}
          </div>

          <div className="mt-7 border-t border-[#edf0f3] pt-6">
            <h3 className="text-sm font-bold text-[#40556b]">Ajouter des scanners</h3>

            {!canAssign ? (
              <p className="mt-3 rounded-2xl border border-[#e5e9ee] bg-[#f8fafc] px-4 py-4 text-sm leading-6 text-[#748397]">
                Les nouvelles affectations sont disponibles uniquement pour un événement publié ou
                reporté.
              </p>
            ) : scannersQuery.isPending ? (
              <div className="mt-5">
                <Spinner label="Chargement des scanners disponibles" />
              </div>
            ) : scannersQuery.isError ? (
              <p role="alert" className="mt-4 text-sm font-medium text-red-700">
                Impossible de charger les scanners disponibles.
              </p>
            ) : noScannerAvailable ? (
              <div className="mt-3 rounded-2xl border border-dashed border-[#d7e0e9] bg-[#f8fafc] px-5 py-5">
                <p className="font-semibold text-[#40556b]">
                  Aucun scanner disponible pour une nouvelle affectation.
                </p>

                <p className="mt-2 text-sm leading-6 text-[#7d8c9c]">
                  Invitez un scanner depuis la page Scanners pour pouvoir l’affecter à cet
                  événement.
                </p>
              </div>
            ) : availableScanners.length > 0 ? (
              <div className="mt-3 divide-y divide-[#edf0f3] rounded-2xl border border-[#e3e9ef]">
                {availableScanners.map((scanner) => {
                  const name = scannerName(scanner);

                  const assigning =
                    assignMutation.isPending && assignMutation.variables === scanner.id;

                  return (
                    <div
                      key={scanner.id}
                      className="flex flex-wrap items-center justify-between gap-4 p-4"
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-[#40556b]">{name || scanner.email}</p>

                        <p className="mt-1 break-all text-xs text-[#8492a2]">{scanner.email}</p>

                        <p className="mt-1 text-xs font-semibold text-[#1769d2]">
                          {SCANNER_STATUS_LABELS[scanner.status]}
                        </p>
                      </div>

                      <Button
                        type="button"
                        disabled={assignMutation.isPending || unassignMutation.isPending}
                        aria-label={`Affecter ${name || scanner.email}`}
                        onClick={() => {
                          assignMutation.mutate(scanner.id);
                        }}
                      >
                        {assigning ? "Affectation…" : "Affecter"}
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="mt-3 rounded-2xl border border-dashed border-[#d7e0e9] px-4 py-5 text-sm leading-6 text-[#7d8c9c]">
                Aucun autre scanner affectable n’est disponible. Les invitations annulées, comptes
                supprimés, départs demandés et scanners archivés sont exclus.
              </p>
            )}
          </div>
        </>
      )}
    </Card>
  );
}
