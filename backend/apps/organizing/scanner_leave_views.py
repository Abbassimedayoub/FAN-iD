from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.concurrency import parse_if_match
from apps.core.openapi import ERROR_RESPONSE
from apps.identity.api import IsApprovedOrganizer

from .scanner_leave_serializers import ScannerLeaveAcceptOtpSerializer, ScannerLeaveDecisionSerializer
from .scanner_permissions import OrganizerScannerResourcePermission
from .scanner_security import (
    SCANNER_SECURITY_ACTION_LEAVE_ACCEPT,
    SCANNER_SECURITY_ACTION_LEAVE_REQUEST,
    ScannerSecurityService,
)
from .scanner_security_serializers import ScannerSecurityCodeConfirmSerializer
from .scanner_views import OrganizerScannerMixin
from .services.scanner_leaves import ScannerLeaveService


def _require_scanner_role(
    request: Request,
) -> None:
    role = getattr(request.user, "role", None)
    role_code = getattr(role, "code", role)

    if str(role_code).upper() != "SCANNER":
        raise PermissionDenied()


class ScannerLeaveSecurityCodeView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        operation_id="scanner_leave_security_code_request",
        summary=("Recevoir le code OTP avant de demander " "la suppression de mon accès scanner"),
        request=None,
        responses={
            200: None,
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
    ) -> Response:
        _require_scanner_role(request)

        scanner = ScannerLeaveService.get_request_scanner(
            user_id=request.user.pk,
        )

        result = ScannerSecurityService.request(
            organizer=scanner.organizer,
            scanner_id=scanner.pk,
            requested_by_id=request.user.pk,
            action=(SCANNER_SECURITY_ACTION_LEAVE_REQUEST),
        )

        return Response(
            {
                "challenge_id": str(
                    result.challenge_id,
                ),
                "expires_in_seconds": (result.expires_in_seconds),
            },
            status=status.HTTP_200_OK,
        )


class ScannerLeaveRequestView(APIView):
    permission_classes = [
        IsAuthenticated,
    ]

    @extend_schema(
        operation_id="scanner_leave_request",
        summary=("Confirmer par OTP la demande " "de suppression de mon accès scanner"),
        request=ScannerSecurityCodeConfirmSerializer,
        responses={
            202: None,
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
    ) -> Response:
        _require_scanner_role(request)

        serializer = ScannerSecurityCodeConfirmSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        scanner = ScannerLeaveService.get_request_scanner(
            user_id=request.user.pk,
        )

        updated_scanner = ScannerSecurityService.consume_and_run(
            organizer=scanner.organizer,
            scanner_id=scanner.pk,
            requested_by_id=request.user.pk,
            challenge_id=(serializer.validated_data["challenge_id"]),
            code=serializer.validated_data["code"],
            action=(SCANNER_SECURITY_ACTION_LEAVE_REQUEST),
            expected_version=scanner.version,
            operation=lambda: (
                ScannerLeaveService.request(
                    user_id=request.user.pk,
                )
            ),
        )

        return Response(
            {
                "status": updated_scanner.status,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class OrganizerScannerLeaveDecisionView(
    OrganizerScannerMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerResourcePermission,
    ]

    @extend_schema(
        operation_id="organizer_scanner_leave_decision",
        summary="Accepter ou refuser une demande de départ scanner",
        request=ScannerLeaveDecisionSerializer,
        responses={
            204: None,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            428: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: Request,
        scanner_id: Any,
    ) -> Response:
        organizer = self.get_organizer(request)

        serializer = ScannerLeaveDecisionSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        expected_version = parse_if_match(
            request.headers.get("If-Match"),
        )

        decision = serializer.validated_data["decision"]

        if decision == "ACCEPT":
            otp_serializer = ScannerLeaveAcceptOtpSerializer(
                data=request.data,
            )
            otp_serializer.is_valid(
                raise_exception=True,
            )

            ScannerSecurityService.consume_and_run(
                organizer=organizer,
                scanner_id=scanner_id,
                requested_by_id=request.user.pk,
                challenge_id=otp_serializer.validated_data["challenge_id"],
                code=otp_serializer.validated_data["code"],
                action=(SCANNER_SECURITY_ACTION_LEAVE_ACCEPT),
                expected_version=expected_version,
                operation=lambda: ScannerLeaveService.accept(
                    organizer=organizer,
                    scanner_id=scanner_id,
                    actor_id=request.user.pk,
                    expected_version=expected_version,
                ),
            )
        else:
            ScannerLeaveService.reject(
                organizer=organizer,
                scanner_id=scanner_id,
                actor_id=request.user.pk,
                expected_version=expected_version,
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )
