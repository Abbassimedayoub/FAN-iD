from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import NotFoundBusinessError
from apps.core.openapi import ERROR_RESPONSE
from apps.identity.api import IsApprovedOrganizer

from .models import Organizer
from .scanner_archive_serializers import ScannerBulkArchiveSerializer
from .scanner_permissions import OrganizerScannerResourcePermission
from .services.scanner_archives import ScannerArchiveService
from .views import OrganizerScopedMixin


class OrganizerScannerBulkArchiveView(
    OrganizerScopedMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        OrganizerScannerResourcePermission,
    ]

    @staticmethod
    def get_organizer(request: Request) -> Organizer:
        organizer = Organizer.objects.filter(
            pk=request.organizer_id,
        ).first()

        if organizer is None:
            raise NotFoundBusinessError()

        return organizer

    @extend_schema(
        operation_id="organizers_me_scanners_bulk_archive",
        summary="Supprimer des anciens scanners de la liste",
        request=ScannerBulkArchiveSerializer,
        responses={
            200: None,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = ScannerBulkArchiveSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        archived = ScannerArchiveService.archive_many(
            organizer=self.get_organizer(request),
            actor_id=request.user.pk,
            items=serializer.validated_data["scanners"],
        )

        return Response(
            {"archived": archived},
            status=status.HTTP_200_OK,
        )
