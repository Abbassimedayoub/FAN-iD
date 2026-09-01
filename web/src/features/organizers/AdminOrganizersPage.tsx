import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { AdminOrganizersView } from "./AdminOrganizersView";
import type { OrganizerFilters, OrganizerPage, OrganizerStatus } from "./types";
import { organizerQueryKeys, useOrganizers } from "./useOrganizers";

function sameFilters(left: OrganizerFilters, right: OrganizerFilters): boolean {
  return left.page === right.page && left.validationStatus === right.validationStatus;
}

export function AdminOrganizersPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [page, setPage] = useState(1);

  // Tous les organisateurs sont chargés directement.
  const [validationStatus, setValidationStatus] = useState<OrganizerStatus | undefined>(undefined);

  // La liste compacte affiche les cinq premiers dossiers.
  const [showAll, setShowAll] = useState(false);

  const filters = useMemo<OrganizerFilters>(
    () => ({
      page,
      validationStatus,
    }),
    [page, validationStatus],
  );

  const query = useOrganizers(filters);
  const lastSuccessfulFilters = useRef<OrganizerFilters | null>(null);

  useEffect(() => {
    if (query.isSuccess && query.data && !query.isPlaceholderData) {
      lastSuccessfulFilters.current = filters;
    }
  }, [filters, query.data, query.isPlaceholderData, query.isSuccess]);

  const previousFilters = lastSuccessfulFilters.current;

  const failedDifferentQuery =
    query.isError && previousFilters !== null && !sameFilters(filters, previousFilters);

  const cachedPreviousData = failedDifferentQuery
    ? queryClient.getQueryData<OrganizerPage>(organizerQueryKeys.list(previousFilters))
    : undefined;

  const showingPreviousData = cachedPreviousData !== undefined;

  const visibleData = showingPreviousData ? cachedPreviousData : query.data;

  const displayingPreviousFilters = query.isPlaceholderData || showingPreviousData;

  const displayedFilters = displayingPreviousFilters && previousFilters ? previousFilters : filters;

  function changeValidationStatus(status: OrganizerStatus | undefined): void {
    setPage(1);
    setValidationStatus(status);
    setShowAll(false);
  }

  return (
    <AdminOrganizersView
      validationStatus={validationStatus}
      displayedValidationStatus={displayedFilters.validationStatus}
      data={visibleData}
      visiblePage={displayedFilters.page}
      isPending={query.isPending}
      isFetching={query.isFetching}
      error={query.isError ? query.error : null}
      showingPreviousData={showingPreviousData}
      showAll={showAll}
      onValidationStatusChange={changeValidationStatus}
      onRetry={() => {
        void query.refetch();
      }}
      onShowAll={() => {
        setShowAll(true);
      }}
      onPrevious={() => {
        setPage((current) => Math.max(1, current - 1));
      }}
      onNext={() => {
        setPage((current) => current + 1);
      }}
      onOpenOrganizer={(organizerId) => {
        navigate(`/admin/organizers/${organizerId}`);
      }}
    />
  );
}
