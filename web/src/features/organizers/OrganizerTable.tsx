import { Table } from "@/components/primitives";

import { OrganizerStatusBadge } from "./OrganizerStatusBadge";
import type { Organizer } from "./types";

const DATE_FORMATTER = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "medium",
});

function formatDate(value: string): string {
  return DATE_FORMATTER.format(new Date(value));
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
            Statut
          </th>
          <th scope="col" className="px-3 py-3 font-medium">
            Déposée le
          </th>
        </tr>
      </thead>

      <tbody>
        {organizers.map((organizer) => (
          <tr key={organizer.id} className="border-b border-navy/10 last:border-0">
            <td className="px-3 py-4 font-medium text-navy">
              {onOpenOrganizer ? (
                <button
                  type="button"
                  onClick={() => onOpenOrganizer(organizer.id)}
                  className="min-h-[44px] text-left text-primary underline-offset-4 hover:underline"
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

            <td className="px-3 py-4 text-navy/70">{formatDate(organizer.created_at)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
