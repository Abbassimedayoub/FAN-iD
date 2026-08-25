import { Table } from "@/components/primitives";

import { OrganizerStatusBadge } from "./OrganizerStatusBadge";
import type { Organizer } from "./types";

const DATE_FORMATTER = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "medium",
});

function formatDate(value: string | null): string {
  return value ? DATE_FORMATTER.format(new Date(value)) : "—";
}

function displayValue(value: string | null): string {
  return value && value.trim().length > 0 ? value : "—";
}

function displayCommission(value: string): string {
  const rate = Number(value);

  if (!Number.isFinite(rate)) {
    return value;
  }

  return `${new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 2,
  }).format(rate * 100)} %`;
}

export function OrganizerTable({
  organizers,
  onOpenOrganizer,
}: {
  organizers: readonly Organizer[];
  onOpenOrganizer?: (organizerId: string) => void;
}) {
  return (
    <Table>
      <caption className="sr-only">Dossiers organisateurs</caption>

      <thead>
        <tr className="border-b border-navy/10 text-navy/60">
          <th scope="col" className="px-3 py-3 font-medium">
            Organisateur
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            Contact
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            État
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            N° TVA
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            Commission
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            Inscrit le
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            Validé le
          </th>
        </tr>
      </thead>

      <tbody>
        {organizers.map((organizer) => (
          <tr
            key={organizer.id}
            className="border-b border-navy/10 transition hover:bg-navy/[0.02] last:border-0"
          >
            <td className="px-3 py-4 font-medium text-navy">
              {onOpenOrganizer ? (
                <button
                  type="button"
                  onClick={() => onOpenOrganizer(organizer.id)}
                  className="min-h-[44px] text-left font-semibold text-primary underline-offset-4 hover:underline"
                >
                  {organizer.org_name}
                </button>
              ) : (
                organizer.org_name
              )}
            </td>

            <td className="px-3 py-4 text-navy/70">{organizer.contact_email}</td>

            <td className="px-3 py-4">
              <OrganizerStatusBadge status={organizer.validation_status} />
            </td>

            <td className="px-3 py-4 text-navy/70">{displayValue(organizer.vat_number)}</td>

            <td className="px-3 py-4 text-navy/70">
              {displayCommission(organizer.commission_rate)}
            </td>

            <td className="whitespace-nowrap px-3 py-4 text-navy/70">
              {formatDate(organizer.created_at)}
            </td>

            <td className="whitespace-nowrap px-3 py-4 text-navy/70">
              {formatDate(organizer.validated_at)}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
