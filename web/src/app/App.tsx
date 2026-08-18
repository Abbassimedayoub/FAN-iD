import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Skeleton } from "@/components/Skeleton";
import { toAppError } from "@/lib/errors";
import { httpClient } from "@/lib/httpClient";

interface HealthResponse {
  status: string;
  version: string;
  commit: string;
}

/**
 * Écran de démonstration du Sprint 0 : exerce les CINQ états d'écran
 * (§4.2 Source B) sur l'unique donnée distante disponible à ce stade
 * (`/api/v1/health`). Aucun écran métier — coquille volontairement minimale.
 */
export function App() {
  const { data, isLoading, isRefetching, isError, error, refetch } = useQuery<HealthResponse>({
    queryKey: ["platform-health"],
    queryFn: async () => {
      const response = await httpClient.get<HealthResponse>("/api/v1/health");
      return response.data;
    },
  });

  if (isLoading) {
    return (
      <main className="p-8">
        <Skeleton className="h-8 w-64" aria-label="Chargement du statut de la plateforme" />
      </main>
    );
  }

  if (isError) {
    return (
      <main className="p-8">
        <ErrorState error={toAppError(error)} onRetry={() => refetch()} />
      </main>
    );
  }

  if (!data) {
    return (
      <main className="p-8">
        <EmptyState title="Aucune donnée" description="Le service n'a rien renvoyé." />
      </main>
    );
  }

  return (
    <main className="p-8">
      <h1 className="font-sora text-2xl font-bold text-navy">FAN id — Sprint 0</h1>
      <p className="mt-2 text-navy/70" aria-live={isRefetching ? "polite" : "off"}>
        Statut plateforme : <strong>{data.status}</strong> (version {data.version}, commit {data.commit})
        {isRefetching ? " — actualisation…" : ""}
      </p>
    </main>
  );
}
