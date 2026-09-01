from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import (
    NotFoundBusinessError,
)
from apps.core.openapi import ERROR_RESPONSE
from apps.identity.api import (
    IsApprovedOrganizer,
)

from .models import Organizer
from .scanner_permissions import (
    OrganizerScannerCredentialPermission,
)
from .scanner_serializers import (
    ScannerSerializer,
)
from .services.scanners import (
    ScannerInvitationService,
)
from .views import OrganizerScopedMixin


class OrganizerScannerInvitationResendView(
    OrganizerScopedMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerCredentialPermission,
    ]

    @staticmethod
    def get_organizer(
        request: Request,
    ) -> Organizer:
        organizer = Organizer.objects.filter(
            pk=request.organizer_id,
        ).first()

        if organizer is None:
            raise NotFoundBusinessError()

        return organizer

    @extend_schema(
        operation_id=("organizer_scanner_invitation_resend"),
        summary=("Renvoyer une invitation scanner"),
        responses={
            200: ScannerSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: Request,
        scanner_id: Any,
    ) -> Response:
        scanner = ScannerInvitationService.resend(
            organizer=self.get_organizer(request),
            actor_id=request.user.pk,
            scanner_id=scanner_id,
        )

        return Response(
            ScannerSerializer(scanner).data,
            status=status.HTTP_200_OK,
        )
