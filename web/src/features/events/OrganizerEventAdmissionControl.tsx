import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Spinner } from "@/components/primitives";

import { closeEventAdmission, fetchEventAdmissionStatus, openEventAdmission } from "./api";
import type { OrganizerEvent } from "./types";

export function OrganizerEventAdmissionControl({ event }: { event: OrganizerEvent }) {
  const queryClient = useQueryClient();

  const admissionQuery = useQuery({
    queryKey: ["access", "event", event.id, "admission"],
    queryFn: () => fetchEventAdmissionStatus(event.id),
  });

  const mutation = useMutation({
    mutationFn: (isOpen: boolean) =>
      isOpen ? closeEventAdmission(event.id) : openEventAdmission(event.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["access", "event", event.id, "admission"],
      });
    },
  });

  if (admissionQuery.isPending) {
    return (
      <Card className="p-6 sm:p-8">
        <Spinner label="Chargement du contrôle des entrées" />
      </Card>
    );
  }

  if (admissionQuery.isError || !admissionQuery.data) {
    return (
      <Card className="border-[#f1c8c8] bg-[#fffafa] p-6 sm:p-8">
        <h2 className="font-sora text-lg font-bold text-[#30445b]">Contrôle des entrées</h2>
        <p className="mt-2 text-sm text-[#a14343]">Impossible de charger l’état des entrées.</p>
      </Card>
    );
  }

  const isOpen = admissionQuery.data.is_open;
  const canOpen =
    event.status === "PUBLISHED" ||
    (event.status === "POSTPONED" &&
      event.postponed_to_starts_at !== null &&
      event.postponed_to_ends_at !== null);
  const canControl = isOpen || canOpen;
  const busy = mutation.isPending;

  return (
    <Card className={isOpen ? "border-[#a7dabc] bg-[#f4fff7] p-6 sm:p-8" : "p-6 sm:p-8"}>
      <div className="flex flex-wrap items-center justify-between gap-5">
        <div>
          <h2 className="font-sora text-lg font-bold text-[#30445b]">Contrôle des entrées</h2>
          <p className="mt-2 text-sm text-[#66788b]">
            {isOpen
              ? "Entrées ouvertes : les scanners peuvent valider les billets."
              : canOpen
                ? "Entrées fermées : aucun billet ne peut être validé par les scanners."
                : "Les entrées ne peuvent pas être ouvertes tant qu’une nouvelle date n’est pas définie."}
          </p>
        </div>

        {canControl ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => mutation.mutate(isOpen)}
            className={
              isOpen
                ? "min-h-[44px] rounded-xl border border-[#c95a5a] bg-white px-5 text-sm font-semibold text-[#b13f3f] disabled:opacity-60"
                : "min-h-[44px] rounded-xl bg-[#1769d2] px-5 text-sm font-semibold text-white disabled:opacity-60"
            }
          >
            {busy ? "Mise à jour…" : isOpen ? "Fermer les entrées" : "Ouvrir les entrées"}
          </button>
        ) : null}
      </div>

      {mutation.isError ? (
        <p className="mt-4 text-sm text-[#a14343]">
          La mise à jour des entrées a échoué. Réessayez.
        </p>
      ) : null}
    </Card>
  );
}
