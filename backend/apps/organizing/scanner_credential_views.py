from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import (
    AllowAny,
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
    ScannerCredentialRequestSerializer,
    ScannerPasswordHelpRequestSerializer,
)
from .services.scanner_credentials import (
    ScannerCredentialService,
)
from .views import OrganizerScopedMixin


class ScannerPasswordHelpRequestView(
    APIView,
):
    permission_classes = [
        AllowAny,
    ]

    @extend_schema(
        operation_id=("scanner_password_help_request"),
        request=ScannerPasswordHelpRequestSerializer,
        responses={
            202: None,
            400: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: Request,
    ) -> Response:
        serializer = ScannerPasswordHelpRequestSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        ScannerCredentialService.request_help(
            email=(serializer.validated_data["email"]),
        )

        return Response(
            status=status.HTTP_202_ACCEPTED,
        )


class OrganizerScannerPasswordReissueView(
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
        operation_id=("organizer_scanner_password_reissue"),
        responses={
            200: ScannerCredentialRequestSerializer,
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
        organizer = self.get_organizer(request)

        credential_request = ScannerCredentialService.reissue(
            organizer=organizer,
            scanner_id=scanner_id,
            actor_id=request.user.pk,
        )

        return Response(
            ScannerCredentialRequestSerializer(credential_request).data,
            status=status.HTTP_200_OK,
        )
