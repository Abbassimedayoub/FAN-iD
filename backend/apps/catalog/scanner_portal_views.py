from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.api import Action, ActionPermission
from apps.organizing.api import get_scanner_portal_context

from .api import list_scanner_portal_events
from .scanner_portal_serializers import ScannerPortalEventSerializer


class ScannerAssignedEventListView(APIView):
    """
    Liste opérationnelle du scanner connecté.

    TICKET_SCAN est la capacité métier déjà réservée au rôle SCANNER.
    Cette route ne donne aucun EVENT_READ général : elle filtre ensuite
    strictement sur l'identité scanner et ses affectations actives.
    """

    permission_classes = [
        IsAuthenticated,
        ActionPermission,
    ]
    required_action = Action.TICKET_SCAN

    @extend_schema(
        operation_id="catalog_scanner_assigned_events",
        summary="Lister mes événements affectés",
        responses={
            200: ScannerPortalEventSerializer(
                many=True,
            ),
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        scanner = get_scanner_portal_context(
            user_id=request.user.pk,
        )

        if scanner is None:
            raise PermissionDenied("Le portail scanner n'est pas " "disponible pour ce compte.")

        events = list_scanner_portal_events(
            scanner_id=scanner.id,
            organizer_id=scanner.organizer_id,
        )

        return Response(
            ScannerPortalEventSerializer(
                events,
                many=True,
            ).data,
        )
