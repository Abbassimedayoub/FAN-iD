import { Badge, Button } from "@/components/primitives";

import type { AuthSession } from "./types";

const DATE_FORMATTER = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "medium",
  timeStyle: "short",
});

function formatDate(value: string): string {
  return DATE_FORMATTER.format(new Date(value));
}

interface SessionRowProps {
  session: AuthSession;
  disabled?: boolean;
  isRevoking?: boolean;
  onRevoke: (session: AuthSession) => void;
}

export function SessionRow({
  session,
  disabled = false,
  isRevoking = false,
  onRevoke,
}: SessionRowProps) {
  return (
    <tr className="border-b border-navy/10 last:border-0">
      <td className="px-3 py-4">
        <div className="flex flex-col gap-1">
          <span className="font-medium text-navy">
            {session.device?.label ?? "Appareil inconnu"}
          </span>

          {session.current ? (
            <span>
              <Badge tone="success">Session actuelle</Badge>
            </span>
          ) : null}
        </div>
      </td>

      <td className="px-3 py-4 text-navy/70">{session.ip ?? "—"}</td>

      <td className="max-w-xs px-3 py-4 text-navy/70">
        <span className="break-words">{session.user_agent || "—"}</span>
      </td>

      <td className="px-3 py-4 text-navy/70">{formatDate(session.last_used_at)}</td>

      <td className="px-3 py-4">
        <Button type="button" disabled={disabled} onClick={() => onRevoke(session)}>
          {isRevoking ? "Révocation…" : session.current ? "Déconnecter cette session" : "Révoquer"}
        </Button>
      </td>
    </tr>
  );
}
