from typing import Any

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi import ERROR_RESPONSE
from apps.identity.api import IsApprovedOrganizer

from .scanner_permissions import (
    OrganizerScannerResourcePermission,
)
from .scanner_security import ScannerSecurityService
from .scanner_security_serializers import (
    ScannerSecurityCodeRequestSerializer,
)
from .scanner_views import OrganizerScannerMixin


class OrganizerScannerSecurityCodeView(
    OrganizerScannerMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerResourcePermission,
    ]

    @extend_schema(
        operation_id=(
            "organizer_scanner_security_code_request"
        ),
        summary=(
            "Demander le code OTP avant une action "
            "destructive sur un scanner"
        ),
        request=ScannerSecurityCodeRequestSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "Code envoyé. Retourne challenge_id "
                    "et expires_in_seconds."
                )
            ),
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            429: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: Request,
        scanner_id: Any,
    ) -> Response:
        organizer = self.get_organizer(
            request,
        )

        serializer = (
            ScannerSecurityCodeRequestSerializer(
                data=request.data,
            )
        )
        serializer.is_valid(
            raise_exception=True,
        )

        result = ScannerSecurityService.request(
            organizer=organizer,
            scanner_id=scanner_id,
            requested_by_id=request.user.pk,
            action=serializer.validated_data[
                "action"
            ],
        )

        return Response(
            {
                "challenge_id": str(
                    result.challenge_id,
                ),
                "expires_in_seconds": (
                    result.expires_in_seconds
                ),
            },
            status=status.HTTP_200_OK,
        )
