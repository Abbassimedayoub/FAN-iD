import { useNavigate, useParams } from "react-router-dom";

import { AdminOrganizerDetailView } from "./AdminOrganizerDetailView";
import { useOrganizer } from "./useOrganizer";

export function AdminOrganizerDetailPage() {
  const navigate = useNavigate();
  const { organizerId = "" } = useParams<{ organizerId: string }>();

  const query = useOrganizer(organizerId);

  return (
    <AdminOrganizerDetailView
      data={query.data}
      isPending={query.isPending}
      isFetching={query.isFetching}
      error={query.isError ? query.error : null}
      onRetry={() => {
        void query.refetch();
      }}
      onBack={() => {
        navigate("/admin/organizers");
      }}
    />
  );
}
