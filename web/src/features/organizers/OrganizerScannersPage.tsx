import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { Button, Card, Input, Modal, Spinner } from "@/components/primitives";
import { StepUpDialog } from "@/features/auth/StepUpDialog";
import { toAppError } from "@/lib/errors";

import { fetchMyOrganizer, myOrganizerQueryKey } from "./myOrganizer";
import { OrganizerShell } from "./OrganizerShell";
import {
  archiveOrganizerScanners,
  decideOrganizerScannerLeave,
  fetchOrganizerScannersPage,
  inviteOrganizerScanner,
  organizerScannersQueryKey,
  requestOrganizerScannerSecurityCode,
  revokeOrganizerScanner,
  reissueOrganizerScannerPassword,
  resendOrganizerScannerInvitation,
  type OrganizerScanner,
  type ScannerLeaveDecision,
  type ScannerSecurityAction,
  SCANNER_STATUSES,
  type ScannerSecurityOtp,
  type ScannerStatus,
} from "./scanners";

const STATUS_CONTENT: Record<
  ScannerStatus,
  {
    label: string;
    description: string;
    className: string;
  }
> = {
  INVITED: {
    label: "Invitation créée",
    description: "Le compte scanner est créé. L’envoi des e-mails est en cours.",
    className: "bg-amber-50 text-amber-700 ring-amber-200",
  },
  EMAIL_SENT: {
    label: "Invitation envoyée",
    description: "Le scanner a reçu son adresse e-mail et son mot de passe temporaire.",
    className: "bg-blue-50 text-blue-700 ring-blue-200",
  },
  OPENED: {
    label: "Compte ouvert",
    description:
      "Le scanner s’est connecté. Il doit maintenant changer son mot de passe temporaire.",
    className: "bg-violet-50 text-violet-700 ring-violet-200",
  },
  ACTIVE: {
    label: "Compte actif",
    description: "Le mot de passe temporaire a été remplacé. Le compte est actif.",
    className: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  },
  LEAVE_REQUESTED: {
    label: "Départ demandé",
    description: "Le scanner a demandé la suppression de son accès.",
    className: "bg-orange-50 text-orange-700 ring-orange-200",
  },
  INVITATION_CANCELLED: {
    label: "Invitation annulée",
    description: "Cette invitation a été annulée. L’ancien compte ne peut plus se connecter.",
    className: "bg-slate-100 text-slate-600 ring-slate-200",
  },
  DELETED: {
    label: "Compte supprimé",
    description: "L’accès de ce scanner a été retiré et ses sessions ont été révoquées.",
    className: "bg-slate-100 text-slate-600 ring-slate-200",
  },
};

interface ScannerSecurityStep {
  scanner: OrganizerScanner;
  action: ScannerSecurityAction;
  challengeId: string;
  expiresInSeconds: number;
}

const PROGRESS = ["Créée", "Email envoyé", "Compte ouvert", "Actif"] as const;

const STATUS_ORDER: Record<ScannerStatus, number> = {
  INVITED: 0,
  EMAIL_SENT: 1,
  OPENED: 2,
  ACTIVE: 3,
  LEAVE_REQUESTED: 3,
  INVITATION_CANCELLED: -1,
  DELETED: -1,
};

function formatDate(value: string | null): string {
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

function initials(scanner: OrganizerScanner): string {
  return (
    [scanner.first_name, scanner.last_name]
      .filter(Boolean)
      .map((value) => value[0]?.toUpperCase())
      .join("")
      .slice(0, 2) || "SC"
  );
}

function ScannerProgress({ scanner }: { scanner: OrganizerScanner }) {
  const current = STATUS_ORDER[scanner.status];

  if (current < 0) {
    return null;
  }

  return (
    <div className="mt-5">
      <div className="grid grid-cols-4 gap-2">
        {PROGRESS.map((label, index) => {
          const done = index <= current;

          return (
            <div key={label} className="min-w-0">
              <div
                className={["h-1.5 rounded-full", done ? "bg-[#1769d2]" : "bg-[#e7ecf2]"].join(" ")}
              />

              <p
                className={[
                  "mt-2 truncate text-[11px] font-semibold",
                  done ? "text-[#1769d2]" : "text-[#9aa6b4]",
                ].join(" ")}
              >
                {label}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function isPreActive(scanner: OrganizerScanner): boolean {
  return (
    scanner.status === "INVITED" || scanner.status === "EMAIL_SENT" || scanner.status === "OPENED"
  );
}

function canRevoke(scanner: OrganizerScanner): boolean {
  return (
    scanner.status !== "LEAVE_REQUESTED" &&
    scanner.status !== "INVITATION_CANCELLED" &&
    scanner.status !== "DELETED"
  );
}

function ScannerCard({
  scanner,
  onRevoke,
  onLeaveDecision,
  onReissuePassword,
  onResendInvitation,
  revokePending,
  leaveDecisionPending,
  reissuePending,
  resendPending,
  resendError,
  archiveSelected,
  onArchiveSelectionChange,
}: {
  scanner: OrganizerScanner;
  onRevoke: (scanner: OrganizerScanner) => void;
  onLeaveDecision: (scanner: OrganizerScanner, decision: ScannerLeaveDecision) => void;
  onReissuePassword: (scanner: OrganizerScanner) => void;
  onResendInvitation: (scanner: OrganizerScanner) => void;
  revokePending: boolean;
  leaveDecisionPending: boolean;
  reissuePending: boolean;
  resendPending: boolean;
  resendError: string | null;
  archiveSelected: boolean;
  onArchiveSelectionChange: (scanner: OrganizerScanner, selected: boolean) => void;
}) {
  const status = STATUS_CONTENT[scanner.status];
  const archivable = scanner.status === "INVITATION_CANCELLED" || scanner.status === "DELETED";

  return (
    <Card className="border-[#e0e7ee] p-5 shadow-[0_10px_28px_rgba(23,45,74,0.05)]">
      <div className="flex items-start gap-4">
        {archivable ? (
          <label className="mt-3 flex shrink-0 items-center">
            <input
              type="checkbox"
              checked={archiveSelected}
              onChange={(event) => onArchiveSelectionChange(scanner, event.target.checked)}
              aria-label={`Sélectionner ${scanner.first_name} ${scanner.last_name}`}
              className="h-4 w-4 rounded border-slate-300"
            />
          </label>
        ) : null}

        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#e8f2ff] text-sm font-bold text-[#1769d2]">
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
                  {scanner.phone?.trim() || "À renseigner"}
                </span>
              </p>
            </div>

            <span
              className={`inline-flex shrink-0 rounded-full px-3 py-1 text-xs font-bold ring-1 ring-inset ${status.className}`}
            >
              {status.label}
            </span>
          </div>

          <p className="mt-3 text-sm leading-6 text-[#718195]">{status.description}</p>

          {scanner.password_help_pending ? (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-bold text-amber-900">Nouveau mot de passe demandé</p>

              <p className="mt-1 text-xs leading-5 text-amber-800">
                {scanner.password_help_requested_at
                  ? `Demande reçue ${formatDate(scanner.password_help_requested_at)}.`
                  : "Une demande est en attente."}{" "}
                Le nouveau mot de passe sera valable 5 minutes.
              </p>

              <Button
                type="button"
                disabled={reissuePending}
                onClick={() => onReissuePassword(scanner)}
                className="mt-3 bg-amber-600 font-semibold text-white hover:bg-amber-700"
              >
                {reissuePending ? "Envoi…" : "Renvoyer un nouveau mot de passe"}
              </Button>
            </div>
          ) : null}

          {scanner.status === "LEAVE_REQUESTED" ? (
            <div className="mt-5 rounded-xl border border-orange-200 bg-orange-50 p-4">
              <p className="text-sm font-bold text-orange-900">
                Demande de suppression de l’accès scanner
              </p>

              <p className="mt-1 text-xs leading-5 text-orange-800">
                Ce scanner souhaite quitter votre équipe. Acceptez la demande pour retirer
                définitivement son accès, ou refusez-la pour conserver son compte actif.
              </p>

              <div className="mt-4 flex flex-wrap gap-3">
                <Button
                  type="button"
                  disabled={leaveDecisionPending}
                  onClick={() => onLeaveDecision(scanner, "REJECT")}
                  className="border border-orange-300 bg-white font-semibold text-orange-800 hover:bg-orange-100"
                >
                  Refuser
                </Button>

                <Button
                  type="button"
                  disabled={leaveDecisionPending}
                  onClick={() => onLeaveDecision(scanner, "ACCEPT")}
                  className="bg-red-600 font-semibold text-white hover:bg-red-700"
                >
                  Accepter
                </Button>
              </div>
            </div>
          ) : null}

          <ScannerProgress scanner={scanner} />

          <dl className="mt-5 grid gap-3 border-t border-[#edf0f3] pt-4 text-xs sm:grid-cols-2">
            <div>
              <dt className="text-[#9aa6b4]">Invitation créée</dt>
              <dd className="mt-1 font-semibold text-[#536579]">
                {formatDate(scanner.created_at)}
              </dd>
            </div>

            <div>
              <dt className="text-[#9aa6b4]">Email scanner</dt>
              <dd className="mt-1 font-semibold text-[#536579]">
                {formatDate(scanner.scanner_email_sent_at)}
              </dd>
            </div>

            <div>
              <dt className="text-[#9aa6b4]">Première connexion</dt>
              <dd className="mt-1 font-semibold text-[#536579]">{formatDate(scanner.opened_at)}</dd>
            </div>

            <div>
              <dt className="text-[#9aa6b4]">Activation</dt>
              <dd className="mt-1 font-semibold text-[#536579]">
                {formatDate(scanner.activated_at)}
              </dd>
            </div>

            {scanner.removed_at ? (
              <div>
                <dt className="text-[#9aa6b4]">Retrait</dt>
                <dd className="mt-1 font-semibold text-[#536579]">
                  {formatDate(scanner.removed_at)}
                </dd>
              </div>
            ) : null}
          </dl>

          {canRevoke(scanner) ? (
            <div className="mt-5 flex flex-wrap gap-3 border-t border-[#edf0f3] pt-4">
              {isPreActive(scanner) ? (
                <Button
                  type="button"
                  disabled={resendPending}
                  onClick={() => onResendInvitation(scanner)}
                  className="border border-blue-200 bg-white font-semibold text-[#1769d2] hover:bg-blue-50"
                >
                  {resendPending ? "Renvoi…" : "Renvoyer l’invitation"}
                </Button>
              ) : null}

              <Button
                type="button"
                disabled={revokePending || resendPending}
                onClick={() => onRevoke(scanner)}
                className="border border-red-200 bg-white font-semibold text-red-700 hover:bg-red-50"
              >
                {isPreActive(scanner) ? "Annuler l’invitation" : "Retirer le scanner"}
              </Button>
            </div>
          ) : null}

          {resendError ? (
            <p
              role="alert"
              className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {resendError}
            </p>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

export function OrganizerScannersPage() {
  const queryClient = useQueryClient();

  const [firstName, setFirstName] = useState("");

  const [lastName, setLastName] = useState("");

  const [email, setEmail] = useState("");

  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [selectedScanner, setSelectedScanner] = useState<OrganizerScanner | null>(null);

  const [leaveDecisionScanner, setLeaveDecisionScanner] = useState<OrganizerScanner | null>(null);

  const [leaveDecision, setLeaveDecision] = useState<ScannerLeaveDecision | null>(null);

  const [securityStep, setSecurityStep] = useState<ScannerSecurityStep | null>(null);
  const [securityError, setSecurityError] = useState<string | null>(null);

  const [archiveSelection, setArchiveSelection] = useState<string[]>([]);
  const [archiveModalOpen, setArchiveModalOpen] = useState(false);

  const [scannerPage, setScannerPage] = useState(1);
  const [scannerSearch, setScannerSearch] = useState("");
  const [scannerStatus, setScannerStatus] = useState<ScannerStatus | "">("");

  const organizerQuery = useQuery({
    queryKey: myOrganizerQueryKey,
    queryFn: fetchMyOrganizer,
  });

  const approved = organizerQuery.data?.validation_status === "APPROVED";

  const scannersQuery = useQuery({
    queryKey: [
      ...organizerScannersQueryKey,
      {
        page: scannerPage,
        search: scannerSearch.trim(),
        status: scannerStatus,
      },
    ],
    queryFn: () =>
      fetchOrganizerScannersPage({
        page: scannerPage,
        search: scannerSearch,
        status: scannerStatus || undefined,
      }),
    enabled: approved,
    refetchInterval: (query) => {
      const scanners = query.state.data?.results ?? [];

      const pending = scanners.some(
        (scanner) =>
          scanner.status === "INVITED" ||
          scanner.status === "EMAIL_SENT" ||
          scanner.status === "OPENED",
      );

      return pending ? 5000 : false;
    },
  });

  const invitation = useMutation({
    mutationFn: inviteOrganizerScanner,
    onSuccess: async (scanner) => {
      setFirstName("");
      setLastName("");
      setEmail("");

      setSuccessMessage(`Invitation créée pour ${scanner.first_name} ${scanner.last_name}.`);
      setScannerPage(1);

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  const securityCodeRequest = useMutation({
    mutationFn: ({
      scanner,
      action,
    }: {
      scanner: OrganizerScanner;
      action: ScannerSecurityAction;
    }) => requestOrganizerScannerSecurityCode(scanner, action),

    onSuccess: (challenge, variables) => {
      setSecurityError(null);

      setSecurityStep({
        scanner: variables.scanner,
        action: variables.action,
        challengeId: challenge.challenge_id,
        expiresInSeconds: challenge.expires_in_seconds,
      });

      setSelectedScanner(null);
      setLeaveDecisionScanner(null);
      setLeaveDecision(null);
    },
  });

  const revocation = useMutation({
    mutationFn: ({ scanner, otp }: { scanner: OrganizerScanner; otp: ScannerSecurityOtp }) =>
      revokeOrganizerScanner(scanner, otp),

    onSuccess: async (_, variables) => {
      setSuccessMessage(isPreActive(variables.scanner) ? "Invitation annulée." : "Scanner retiré.");

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  const leaveDecisionMutation = useMutation({
    mutationFn: ({
      scanner,
      decision,
      otp,
    }: {
      scanner: OrganizerScanner;
      decision: ScannerLeaveDecision;
      otp?: ScannerSecurityOtp;
    }) => decideOrganizerScannerLeave(scanner, decision, otp),

    onSuccess: async (_, variables) => {
      setLeaveDecisionScanner(null);
      setLeaveDecision(null);

      setSuccessMessage(
        variables.decision === "ACCEPT"
          ? "Demande acceptée. Le scanner a été retiré et ses sessions ont été révoquées."
          : "Demande refusée. Le scanner reste actif.",
      );

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  const archiveMutation = useMutation({
    mutationFn: archiveOrganizerScanners,
    onSuccess: async (result) => {
      setArchiveModalOpen(false);
      setArchiveSelection([]);
      setSuccessMessage(
        `${result.archived} ancien${result.archived > 1 ? "s" : ""} scanner${
          result.archived > 1 ? "s" : ""
        } supprimé${result.archived > 1 ? "s" : ""} de la liste.`,
      );

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  const invitationResend = useMutation({
    mutationFn: resendOrganizerScannerInvitation,
    onSuccess: async (_, scanner) => {
      setSuccessMessage(
        `Invitation renvoyée à ${scanner.first_name} ${scanner.last_name}. Un nouveau mot de passe temporaire valable 5 minutes a été généré.`,
      );

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  const passwordReissue = useMutation({
    mutationFn: reissueOrganizerScannerPassword,
    onSuccess: async () => {
      setSuccessMessage(
        "Le nouveau mot de passe temporaire a été généré. Il est valable 5 minutes et son envoi au scanner est en cours.",
      );

      await queryClient.invalidateQueries({
        queryKey: organizerScannersQueryKey,
      });
    },
  });

  function openLeaveDecision(scanner: OrganizerScanner, decision: ScannerLeaveDecision): void {
    leaveDecisionMutation.reset();
    securityCodeRequest.reset();
    setSecurityError(null);
    setSecurityStep(null);
    setSuccessMessage(null);
    setLeaveDecisionScanner(scanner);
    setLeaveDecision(decision);
  }

  function closeLeaveDecision(): void {
    if (leaveDecisionMutation.isPending || securityCodeRequest.isPending) {
      return;
    }

    leaveDecisionMutation.reset();
    securityCodeRequest.reset();
    setLeaveDecisionScanner(null);
    setLeaveDecision(null);
  }

  function openRevocation(scanner: OrganizerScanner): void {
    revocation.reset();
    securityCodeRequest.reset();
    setSecurityError(null);
    setSecurityStep(null);
    setSuccessMessage(null);
    setSelectedScanner(scanner);
  }

  function closeRevocation(): void {
    if (revocation.isPending || securityCodeRequest.isPending) {
      return;
    }

    revocation.reset();
    securityCodeRequest.reset();
    setSelectedScanner(null);
  }

  function closeSecurityStep(): void {
    revocation.reset();
    leaveDecisionMutation.reset();
    securityCodeRequest.reset();
    setSecurityError(null);
    setSecurityStep(null);
  }

  async function confirmSecurityCode(code: string): Promise<boolean> {
    if (!securityStep) {
      return false;
    }

    setSecurityError(null);

    const otp: ScannerSecurityOtp = {
      challenge_id: securityStep.challengeId,
      code,
    };

    try {
      if (securityStep.action === "REVOKE") {
        await revocation.mutateAsync({
          scanner: securityStep.scanner,
          otp,
        });
      } else {
        await leaveDecisionMutation.mutateAsync({
          scanner: securityStep.scanner,
          decision: "ACCEPT",
          otp,
        });
      }

      return true;
    } catch (error) {
      setSecurityError(toAppError(error).message);

      return false;
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    setSuccessMessage(null);
    invitation.reset();

    if (!firstName.trim() || !lastName.trim() || !email.trim()) {
      return;
    }

    invitation.mutate({
      first_name: firstName,
      last_name: lastName,
      email,
    });
  }

  const breadcrumbs = <span className="text-sm font-semibold text-[#34465c]">Scanners</span>;

  if (organizerQuery.isPending) {
    return (
      <OrganizerShell activeItem="scanners" breadcrumbs={breadcrumbs}>
        <div className="flex min-h-[520px] items-center justify-center">
          <Spinner label="Chargement des scanners" />
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
            Votre compte organisateur doit être approuvé avant de gérer des scanners.
          </Card>
        </main>
      </OrganizerShell>
    );
  }

  const scannerPageData = scannersQuery.data;
  const scanners = scannerPageData?.results ?? [];
  const scannerCount = scannerPageData?.count ?? 0;
  const scannerTotalPages = Math.max(
    1,
    Math.ceil(scannerCount / 5),
  );

  const archivedCandidates = scanners.filter(
    (scanner) => scanner.status === "INVITATION_CANCELLED" || scanner.status === "DELETED",
  );
  const selectedArchivedScanners = archivedCandidates.filter((scanner) =>
    archiveSelection.includes(scanner.id),
  );
  const allArchivedSelected =
    archivedCandidates.length > 0 &&
    archivedCandidates.every((scanner) => archiveSelection.includes(scanner.id));

  function toggleArchiveScanner(scanner: OrganizerScanner, selected: boolean): void {
    setArchiveSelection((current) =>
      selected
        ? current.includes(scanner.id)
          ? current
          : [...current, scanner.id]
        : current.filter((id) => id !== scanner.id),
    );
  }

  function toggleAllArchived(): void {
    if (allArchivedSelected) {
      setArchiveSelection([]);
      return;
    }

    setArchiveSelection(archivedCandidates.map((scanner) => scanner.id));
  }

  return (
    <OrganizerShell activeItem="scanners" breadcrumbs={breadcrumbs}>
      <main className="p-5 sm:p-7 lg:p-10">
        <div className="mx-auto max-w-[1180px]">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#1769d2]">
                Contrôle d’accès
              </p>

              <h1 className="mt-2 font-sora text-3xl font-bold tracking-[-0.03em] text-[#25394f]">
                Scanners
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#718195]">
                Invitez vos équipes et gérez leurs accès scanner.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Link
                to="/organizer/scanners/archives"
                className="rounded-xl border border-[#dfe7ef] bg-white px-4 py-2 text-xs font-bold text-[#1769d2] shadow-sm transition hover:bg-blue-50"
              >
                Voir les archives
              </Link>

              <div className="rounded-xl border border-[#dfe7ef] bg-white px-4 py-2 text-xs font-medium text-[#718195] shadow-sm">
                Actualisation automatique
              </div>
            </div>
          </div>

          {successMessage ? (
            <div
              role="status"
              className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
            >
              {successMessage}
            </div>
          ) : null}

          <div className="mt-8 grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
            <Card className="h-fit border-[#dfe6ed] p-6 lg:sticky lg:top-24">
              <h2 className="font-sora text-lg font-bold text-[#293c52]">Inviter un scanner</h2>

              <p className="mt-2 text-sm leading-6 text-[#718195]">
                Le mot de passe temporaire sera envoyé directement au scanner.
              </p>

              <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                <label htmlFor="scanner-first-name" className="block">
                  <span className="mb-2 block text-sm font-semibold text-[#40546a]">Prénom</span>
                  <Input
                    id="scanner-first-name"
                    autoComplete="given-name"
                    value={firstName}
                    onChange={(event) => setFirstName(event.target.value)}
                    required
                    className="w-full"
                  />
                </label>

                <label htmlFor="scanner-last-name" className="block">
                  <span className="mb-2 block text-sm font-semibold text-[#40546a]">Nom</span>
                  <Input
                    id="scanner-last-name"
                    autoComplete="family-name"
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                    required
                    className="w-full"
                  />
                </label>

                <label htmlFor="scanner-email" className="block">
                  <span className="mb-2 block text-sm font-semibold text-[#40546a]">Email</span>
                  <Input
                    id="scanner-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    className="w-full"
                  />
                </label>

                {invitation.isError ? (
                  <p role="alert" className="text-sm text-red-700">
                    {toAppError(invitation.error).message}
                  </p>
                ) : null}

                <Button
                  type="submit"
                  disabled={invitation.isPending}
                  className="w-full bg-[#1769d2] font-semibold text-white"
                >
                  {invitation.isPending ? "Création…" : "Inviter le scanner"}
                </Button>
              </form>
            </Card>

            <section>
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="font-sora text-xl font-bold text-[#293c52]">Équipe scanner</h2>

                  <p className="mt-1 text-sm text-[#8995a3]">
                    {scannerCount} {scannerCount > 1 ? "comptes" : "compte"}
                  </p>
                </div>

                {scannersQuery.isFetching ? (
                  <span className="text-xs text-[#718195]">Mise à jour…</span>
                ) : null}
              </div>

              <Card className="mb-4 border-[#dfe6ed] p-4">
                <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_240px]">
                  <label htmlFor="scanner-search" className="block">
                    <span className="mb-2 block text-sm font-semibold text-[#40546a]">
                      Rechercher
                    </span>

                    <Input
                      id="scanner-search"
                      type="search"
                      value={scannerSearch}
                      placeholder="Nom, prénom ou e-mail"
                      onChange={(event) => {
                        setScannerSearch(event.target.value);
                        setScannerPage(1);
                        setArchiveSelection([]);
                      }}
                      className="w-full"
                    />
                  </label>

                  <label htmlFor="scanner-status-filter" className="block">
                    <span className="mb-2 block text-sm font-semibold text-[#40546a]">
                      État
                    </span>

                    <select
                      id="scanner-status-filter"
                      value={scannerStatus}
                      onChange={(event) => {
                        setScannerStatus(
                          event.target.value as ScannerStatus | "",
                        );
                        setScannerPage(1);
                        setArchiveSelection([]);
                      }}
                      className="min-h-[44px] w-full rounded-xl border border-[#d7e0e9] bg-white px-4 py-2.5 text-navy shadow-sm outline-none transition hover:border-navy/25 focus:border-cyan focus:ring-4 focus:ring-cyan/10"
                    >
                      <option value="">Tous les états</option>

                      {SCANNER_STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {STATUS_CONTENT[status].label}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </Card>

              {scannersQuery.isPending ? (
                <Card className="flex min-h-[300px] items-center justify-center">
                  <Spinner label="Chargement des scanners" />
                </Card>
              ) : null}

              {scannersQuery.isError ? (
                <Card className="p-8 text-center">
                  <p role="alert" className="text-sm text-red-700">
                    {toAppError(scannersQuery.error).message}
                  </p>

                  <Button
                    type="button"
                    className="mt-4"
                    onClick={() => {
                      void scannersQuery.refetch();
                    }}
                  >
                    Réessayer
                  </Button>
                </Card>
              ) : null}

              {!scannersQuery.isPending && !scannersQuery.isError && scanners.length === 0 ? (
                <Card className="p-10 text-center">
                  <h3 className="font-sora text-lg font-bold text-[#293c52]">
                    {scannerSearch.trim() || scannerStatus
                      ? "Aucun scanner correspondant"
                      : "Aucun scanner"}
                  </h3>

                  {scannerSearch.trim() || scannerStatus ? (
                    <p className="mt-2 text-sm text-[#718195]">
                      Modifiez la recherche ou l’état sélectionné.
                    </p>
                  ) : null}
                </Card>
              ) : null}

              {!scannersQuery.isError && scanners.length > 0 ? (
                <div className="space-y-4">
                  {archivedCandidates.length > 0 ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <label className="flex items-center gap-2 text-sm font-semibold text-[#40546a]">
                        <input
                          type="checkbox"
                          checked={allArchivedSelected}
                          onChange={toggleAllArchived}
                          className="h-4 w-4 rounded border-slate-300"
                        />
                        Sélectionner tous les anciens scanners
                      </label>

                      <Button
                        type="button"
                        disabled={archiveSelection.length === 0}
                        onClick={() => {
                          archiveMutation.reset();
                          setArchiveModalOpen(true);
                        }}
                        className="border border-red-200 bg-white font-semibold text-red-700 hover:bg-red-50"
                      >
                        Supprimer la sélection ({archiveSelection.length})
                      </Button>
                    </div>
                  ) : null}
                  {scanners.map((scanner) => (
                    <ScannerCard
                      key={scanner.id}
                      scanner={scanner}
                      archiveSelected={archiveSelection.includes(scanner.id)}
                      onArchiveSelectionChange={toggleArchiveScanner}
                      onRevoke={openRevocation}
                      onLeaveDecision={openLeaveDecision}
                      onReissuePassword={(scanner) => {
                        setSuccessMessage(null);
                        passwordReissue.reset();
                        passwordReissue.mutate(scanner);
                      }}
                      onResendInvitation={(scanner) => {
                        setSuccessMessage(null);
                        invitationResend.reset();
                        invitationResend.mutate(scanner);
                      }}
                      revokePending={revocation.isPending && selectedScanner?.id === scanner.id}
                      leaveDecisionPending={
                        leaveDecisionMutation.isPending && leaveDecisionScanner?.id === scanner.id
                      }
                      reissuePending={
                        passwordReissue.isPending && passwordReissue.variables?.id === scanner.id
                      }
                      resendPending={
                        invitationResend.isPending && invitationResend.variables?.id === scanner.id
                      }
                      resendError={
                        invitationResend.isError && invitationResend.variables?.id === scanner.id
                          ? toAppError(invitationResend.error).message
                          : null
                      }
                    />
                  ))}

                  <div className="flex flex-col gap-3 rounded-xl border border-[#dfe6ed] bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm font-medium text-[#617286]">
                      Page {scannerPage} sur {scannerTotalPages}
                    </p>

                    <div className="flex gap-3">
                      <Button
                        type="button"
                        disabled={
                          scannerPage <= 1 ||
                          scannerPageData?.previous == null ||
                          scannersQuery.isFetching
                        }
                        onClick={() => {
                          setScannerPage((current) =>
                            Math.max(1, current - 1),
                          );
                          setArchiveSelection([]);
                        }}
                        className="border border-[#d7e0e9] bg-white font-semibold text-[#40546a] hover:bg-slate-50"
                      >
                        Précédent
                      </Button>

                      <Button
                        type="button"
                        disabled={
                          scannerPage >= scannerTotalPages ||
                          scannerPageData?.next == null ||
                          scannersQuery.isFetching
                        }
                        onClick={() => {
                          setScannerPage((current) =>
                            Math.min(
                              scannerTotalPages,
                              current + 1,
                            ),
                          );
                          setArchiveSelection([]);
                        }}
                        className="bg-[#1769d2] font-semibold text-white"
                      >
                        Suivant
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        </div>
      </main>

      <Modal
        open={archiveModalOpen}
        onClose={() => {
          if (!archiveMutation.isPending) {
            setArchiveModalOpen(false);
          }
        }}
        title="Supprimer les anciens scanners de la liste"
      >
        <div className="space-y-4">
          <p className="text-sm leading-6 text-[#617286]">
            Vous allez retirer {selectedArchivedScanners.length} ancien
            {selectedArchivedScanners.length > 1 ? "s" : ""} scanner
            {selectedArchivedScanners.length > 1 ? "s" : ""} de cette liste. Leur historique
            technique et d’audit sera conservé.
          </p>

          {archiveMutation.isError ? (
            <p role="alert" className="text-sm text-red-700">
              {toAppError(archiveMutation.error).message}
            </p>
          ) : null}

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              disabled={archiveMutation.isPending}
              onClick={() => setArchiveModalOpen(false)}
            >
              Annuler
            </Button>

            <Button
              type="button"
              disabled={archiveMutation.isPending || selectedArchivedScanners.length === 0}
              onClick={() => archiveMutation.mutate(selectedArchivedScanners)}
              className="bg-red-600 font-semibold text-white hover:bg-red-700"
            >
              {archiveMutation.isPending
                ? "Suppression…"
                : `Supprimer ${selectedArchivedScanners.length}`}
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        open={leaveDecisionScanner !== null && leaveDecision !== null}
        onClose={closeLeaveDecision}
        title={
          leaveDecision === "ACCEPT"
            ? "Accepter la demande de départ"
            : "Refuser la demande de départ"
        }
      >
        {leaveDecisionScanner && leaveDecision ? (
          <div>
            <p className="text-sm leading-6 text-[#65778b]">
              {leaveDecision === "ACCEPT"
                ? `Vous allez accepter la demande de ${leaveDecisionScanner.first_name} ${leaveDecisionScanner.last_name}. Son accès scanner sera désactivé et ses sessions seront révoquées.`
                : `Vous allez refuser la demande de ${leaveDecisionScanner.first_name} ${leaveDecisionScanner.last_name}. Son compte scanner restera actif.`}
            </p>

            <p className="mt-3 text-sm font-semibold text-[#40546a]">
              Le scanner sera informé de votre décision.
            </p>

            {leaveDecisionMutation.isError ? (
              <p
                role="alert"
                className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {toAppError(leaveDecisionMutation.error).message}
              </p>
            ) : null}

            {securityCodeRequest.isError ? (
              <p
                role="alert"
                className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {toAppError(securityCodeRequest.error).message}
              </p>
            ) : null}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button
                type="button"
                disabled={leaveDecisionMutation.isPending || securityCodeRequest.isPending}
                onClick={closeLeaveDecision}
                className="border border-[#d6dfe8] bg-white font-semibold text-[#536579]"
              >
                Annuler
              </Button>

              <Button
                type="button"
                disabled={leaveDecisionMutation.isPending || securityCodeRequest.isPending}
                onClick={() => {
                  if (leaveDecision === "ACCEPT") {
                    securityCodeRequest.mutate({
                      scanner: leaveDecisionScanner,
                      action: "LEAVE_ACCEPT",
                    });
                    return;
                  }

                  leaveDecisionMutation.mutate({
                    scanner: leaveDecisionScanner,
                    decision: "REJECT",
                  });
                }}
                className={
                  leaveDecision === "ACCEPT"
                    ? "bg-red-600 font-semibold text-white hover:bg-red-700"
                    : "bg-orange-600 font-semibold text-white hover:bg-orange-700"
                }
              >
                {leaveDecisionMutation.isPending || securityCodeRequest.isPending
                  ? "Traitement…"
                  : leaveDecision === "ACCEPT"
                    ? "Recevoir le code et continuer"
                    : "Refuser la demande"}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={selectedScanner !== null}
        onClose={closeRevocation}
        title={
          selectedScanner && isPreActive(selectedScanner)
            ? "Annuler l’invitation"
            : "Retirer le scanner"
        }
      >
        {selectedScanner ? (
          <div>
            <p className="text-sm leading-6 text-[#65778b]">
              {isPreActive(selectedScanner)
                ? `Voulez-vous annuler l’invitation de ${selectedScanner.first_name} ${selectedScanner.last_name} ? Le compte temporaire sera désactivé immédiatement.`
                : `Voulez-vous retirer ${selectedScanner.first_name} ${selectedScanner.last_name} ? Toutes ses sessions scanner seront révoquées immédiatement.`}
            </p>

            <p className="mt-3 text-sm font-semibold text-[#40546a]">
              L’adresse {selectedScanner.email} pourra être utilisée pour une nouvelle invitation.
            </p>

            {revocation.isError ? (
              <p
                role="alert"
                className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {toAppError(revocation.error).message}
              </p>
            ) : null}

            {securityCodeRequest.isError ? (
              <p
                role="alert"
                className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {toAppError(securityCodeRequest.error).message}
              </p>
            ) : null}

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button
                type="button"
                disabled={revocation.isPending || securityCodeRequest.isPending}
                onClick={closeRevocation}
                className="border border-[#d6dfe8] bg-white font-semibold text-[#536579]"
              >
                Fermer
              </Button>

              <Button
                type="button"
                disabled={revocation.isPending || securityCodeRequest.isPending}
                onClick={() => {
                  securityCodeRequest.mutate({
                    scanner: selectedScanner,
                    action: "REVOKE",
                  });
                }}
                className="bg-red-600 font-semibold text-white hover:bg-red-700"
              >
                {securityCodeRequest.isPending ? "Envoi du code…" : "Recevoir le code et continuer"}
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <StepUpDialog
        open={securityStep !== null}
        expiresInSeconds={securityStep?.expiresInSeconds ?? 300}
        error={securityError}
        onClose={closeSecurityStep}
        onConfirm={confirmSecurityCode}
      />
    </OrganizerShell>
  );
}
