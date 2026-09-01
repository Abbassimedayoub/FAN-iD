from typing import Any

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.concurrency import parse_if_match
from apps.core.exceptions import NotFoundBusinessError
from apps.identity.api import Action, ActionPermission

from .models import Organizer, OrganizerReactivationRequest
from .reactivation_serializers import (
    OrganizerReactivationRejectSerializer,
    OrganizerReactivationRequestSerializer,
)
from .reactivation_service import OrganizerReactivationService


def _my_organizer(
    request: Request,
) -> Organizer:
    organizer = Organizer.objects.filter(user=request.user).first()

    if organizer is None:
        raise NotFoundBusinessError()

    return organizer


def _organizer(
    organizer_id: Any,
) -> Organizer:
    organizer = Organizer.objects.filter(pk=organizer_id).first()

    if organizer is None:
        raise NotFoundBusinessError()

    return organizer


def _latest_request(
    organizer: Organizer,
) -> OrganizerReactivationRequest | None:
    return OrganizerReactivationRequest.objects.filter(organizer=organizer).order_by("-created_at").first()


class OrganizerReactivationRequestView(APIView):
    """
    Lecture/création de la demande du propre organisateur.

    Cette route ne réactive jamais le compte.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request: Request,
    ) -> Response:
        organizer = _my_organizer(request)

        item = _latest_request(organizer)

        return Response(
            {"request": (OrganizerReactivationRequestSerializer(item).data if item is not None else None)},
            status=status.HTTP_200_OK,
        )

    def post(
        self,
        request: Request,
    ) -> Response:
        organizer = _my_organizer(request)

        item, created = OrganizerReactivationService.request(
            organizer_id=organizer.pk,
            requested_by_id=request.user.pk,
        )

        return Response(
            OrganizerReactivationRequestSerializer(item).data,
            status=(status.HTTP_201_CREATED if created else status.HTTP_200_OK),
        )


class AdminOrganizerReactivationRequestView(APIView):
    permission_classes = [
        IsAuthenticated,
        ActionPermission,
    ]
    required_action = Action.ORGANIZER_READ

    def get(
        self,
        request: Request,
        organizer_id: Any,
    ) -> Response:
        organizer = _organizer(
            organizer_id,
        )

        self.check_object_permissions(
            request,
            organizer,
        )

        item = _latest_request(
            organizer,
        )

        return Response(
            {"request": (OrganizerReactivationRequestSerializer(item).data if item is not None else None)},
            status=status.HTTP_200_OK,
        )


class AdminOrganizerReactivationApproveView(APIView):
    """
    Seul ADMIN peut approuver.

    Action.ORGANIZER_APPROVE exige déjà STEP_UP dans
    la matrice d'autorisation : l'admin doit donc
    confirmer l'OTP avant que cette méthode puisse
    effectuer SUSPENDED -> APPROVED.
    """

    permission_classes = [
        IsAuthenticated,
        ActionPermission,
    ]
    required_action = Action.ORGANIZER_APPROVE

    def post(
        self,
        request: Request,
        organizer_id: Any,
    ) -> Response:
        organizer = _organizer(
            organizer_id,
        )

        self.check_object_permissions(
            request,
            organizer,
        )

        expected_version = parse_if_match(request.headers.get("If-Match"))

        item, reopened = OrganizerReactivationService.approve(
            organizer_id=organizer.pk,
            reviewed_by_id=request.user.pk,
            expected_version=expected_version,
        )

        return Response(
            {
                "request": (OrganizerReactivationRequestSerializer(item).data),
                "organizer": {
                    "id": str(reopened.pk),
                    "validation_status": (reopened.validation_status),
                    "version": reopened.version,
                },
            },
            status=status.HTTP_200_OK,
        )


class AdminOrganizerReactivationRejectView(APIView):
    permission_classes = [
        IsAuthenticated,
        ActionPermission,
    ]
    required_action = Action.ORGANIZER_REJECT

    def post(
        self,
        request: Request,
        organizer_id: Any,
    ) -> Response:
        organizer = _organizer(
            organizer_id,
        )

        self.check_object_permissions(
            request,
            organizer,
        )

        serializer = OrganizerReactivationRejectSerializer(
            data=request.data,
        )
        serializer.is_valid(
            raise_exception=True,
        )

        expected_version = parse_if_match(request.headers.get("If-Match"))

        item = OrganizerReactivationService.reject(
            organizer_id=organizer.pk,
            reviewed_by_id=request.user.pk,
            expected_version=expected_version,
            reason=(serializer.validated_data["reason"]),
        )

        return Response(
            {
                "request": (OrganizerReactivationRequestSerializer(item).data),
                "organizer": {
                    "id": str(organizer.pk),
                    "validation_status": (organizer.validation_status),
                    "version": organizer.version,
                },
            },
            status=status.HTTP_200_OK,
        )
