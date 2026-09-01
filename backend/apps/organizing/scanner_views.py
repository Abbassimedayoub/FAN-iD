from typing import Any

from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.concurrency import parse_if_match
from apps.core.exceptions import (
    NotFoundBusinessError,
)
from apps.core.openapi import ERROR_RESPONSE
from apps.identity.api import (
    IsApprovedOrganizer,
)

from .constants import SCANNER_STATUSES
from .models import Organizer, Scanner
from .scanner_permissions import (
    OrganizerScannerCollectionPermission,
    OrganizerScannerResourcePermission,
)
from .scanner_serializers import (
    ScannerInviteSerializer,
    ScannerSerializer,
)
from .scanner_security import (
    SCANNER_SECURITY_ACTION_REVOKE,
    ScannerSecurityService,
)
from .scanner_security_serializers import (
    ScannerSecurityCodeConfirmSerializer,
)
from .services.scanners import (
    ScannerAccessService,
    ScannerInvitationService,
)
from .views import OrganizerScopedMixin


class OrganizerScannerMixin(
    OrganizerScopedMixin,
):
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


class OrganizerScannerPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = None
    max_page_size = 5


class OrganizerScannerCollectionView(
    OrganizerScannerMixin,
    APIView,
):
    """
    GET/POST /api/v1/organizers/me/scanners.
    """

    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerCollectionPermission,
    ]

    @extend_schema(
        operation_id=("organizers_me_scanners_list"),
        summary="Lister mes scanners",
        responses={
            200: ScannerSerializer(many=True),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        organizer = self.get_organizer(request)

        search = request.query_params.get(
            "search",
            "",
        ).strip()

        scanner_status = (
            request.query_params.get(
                "status",
                "",
            )
            .strip()
            .upper()
        )

        if scanner_status and scanner_status not in SCANNER_STATUSES:
            raise ValidationError(
                {
                    "status": [
                        "État scanner invalide.",
                    ],
                }
            )

        scanners = Scanner.objects.filter(
            organizer=organizer,
            archived_at__isnull=True,
        ).select_related("user")

        if search:
            for term in search.split():
                scanners = scanners.filter(
                    Q(invited_first_name__icontains=term)
                    | Q(invited_last_name__icontains=term)
                    | Q(invited_email__icontains=term)
                    | Q(user__first_name__icontains=term)
                    | Q(user__last_name__icontains=term)
                    | Q(user__email__icontains=term)
                )

        if scanner_status:
            scanners = scanners.filter(
                status=scanner_status,
            )

        scanners = scanners.order_by(
            "-created_at",
            "pk",
        )

        paginator = OrganizerScannerPagination()

        page = paginator.paginate_queryset(
            scanners,
            request,
            view=self,
        )

        return paginator.get_paginated_response(
            ScannerSerializer(
                page,
                many=True,
            ).data
        )

    @extend_schema(
        operation_id=("organizers_me_scanners_invite"),
        summary="Inviter un scanner",
        request=ScannerInviteSerializer,
        responses={
            201: ScannerSerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: Request,
    ) -> Response:
        organizer = self.get_organizer(request)

        serializer = ScannerInviteSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        scanner = ScannerInvitationService.invite(
            organizer=organizer,
            actor_id=request.user.pk,
            first_name=(serializer.validated_data["first_name"]),
            last_name=(serializer.validated_data["last_name"]),
            email=(serializer.validated_data["email"]),
        )

        scanner = Scanner.objects.select_related("user").get(pk=scanner.pk)

        return Response(
            ScannerSerializer(scanner).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizerScannerDetailView(
    OrganizerScannerMixin,
    APIView,
):
    """
    DELETE /api/v1/organizers/me/scanners/{id}

    Avant activation :
      INVITATION_CANCELLED.

    Après activation :
      DELETED + révocation immédiate.
    """

    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerResourcePermission,
    ]

    @extend_schema(
        operation_id=("organizers_me_scanners_revoke"),
        summary=("Annuler une invitation ou " "retirer un scanner"),
        responses={
            204: None,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            428: ERROR_RESPONSE,
        },
    )
    def delete(
        self,
        request: Request,
        scanner_id: Any,
    ) -> Response:
        organizer = self.get_organizer(request)

        expected_version = parse_if_match(request.headers.get("If-Match"))

        serializer = ScannerSecurityCodeConfirmSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        ScannerSecurityService.consume_and_run(
            organizer=organizer,
            scanner_id=scanner_id,
            requested_by_id=request.user.pk,
            challenge_id=serializer.validated_data["challenge_id"],
            code=serializer.validated_data["code"],
            action=SCANNER_SECURITY_ACTION_REVOKE,
            expected_version=expected_version,
            operation=lambda: ScannerAccessService.revoke(
                organizer=organizer,
                scanner_id=scanner_id,
                actor_id=request.user.pk,
                expected_version=expected_version,
            ),
        )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class OrganizerArchivedScannerCollectionView(
    OrganizerScannerMixin,
    APIView,
):
    """
    GET /api/v1/organizers/me/scanners/archived.
    """

    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerCollectionPermission,
    ]

    @extend_schema(
        operation_id="organizers_me_scanners_archived_list",
        summary="Lister mes scanners archivés",
        responses={
            200: ScannerSerializer(many=True),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        organizer = self.get_organizer(request)

        search = request.query_params.get(
            "search",
            "",
        ).strip()

        scanner_status = (
            request.query_params.get(
                "status",
                "",
            )
            .strip()
            .upper()
        )

        archive_statuses = {
            "INVITATION_CANCELLED",
            "DELETED",
        }

        if scanner_status and scanner_status not in archive_statuses:
            raise ValidationError(
                {
                    "status": [
                        "État d’archive scanner invalide.",
                    ],
                }
            )

        scanners = Scanner.objects.filter(
            organizer=organizer,
            archived_at__isnull=False,
        ).select_related("user")

        if search:
            for term in search.split():
                scanners = scanners.filter(
                    Q(invited_first_name__icontains=term)
                    | Q(invited_last_name__icontains=term)
                    | Q(invited_email__icontains=term)
                    | Q(user__first_name__icontains=term)
                    | Q(user__last_name__icontains=term)
                    | Q(user__email__icontains=term)
                )

        if scanner_status:
            scanners = scanners.filter(
                status=scanner_status,
            )

        scanners = scanners.order_by(
            "-archived_at",
            "pk",
        )

        paginator = OrganizerScannerPagination()

        page = paginator.paginate_queryset(
            scanners,
            request,
            view=self,
        )

        return paginator.get_paginated_response(
            ScannerSerializer(
                page,
                many=True,
            ).data
        )
