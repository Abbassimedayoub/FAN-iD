"""
Views for the `organizing` context.

This module contains the organizer-scoping mixin and the context's HTTP views.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.concurrency import format_etag, parse_if_match
from apps.core.exceptions import ConflictError
from apps.core.openapi import ERROR_RESPONSE
from apps.core.pagination import StandardPagination
from apps.identity.api import Action, ActionPermission, grant_organizer_role

from .constants import ORGANIZER_APPROVED
from .models import Organizer, OrganizerReactivationRequest
from .permissions import OrganizerRecordPermission
from .serializers import (
    AdminOrganizerListResponseSerializer,
    AdminOrganizerPendingReactivationSerializer,
    OrganizerApplySerializer,
    OrganizerCommissionNegotiationSerializer,
    OrganizerCommissionProposalCreateSerializer,
    OrganizerRejectSerializer,
    OrganizerSerializer,
    organizer_apply_data,
    organizer_commission_negotiation_data,
)
from .services.commissions import OrganizerCommissionService
from .services.onboarding import OrganizerOnboardingService


class OrganizerScopedMixin:
    """
    Attach `request.organizer_id` before DRF evaluates permissions.

    The identity context does not depend on organizing internals, so the owning
    context places a primitive organizer identifier on the request. Doing this
    in `initial()` ensures the value exists before permission checks run. If no
    organizer can be resolved, authorization fails closed.
    """

    def initial(self, request: Any, *args: Any, **kwargs: Any) -> None:
        organizer_id, organizer_approved = self.resolve_organizer_context(request)
        request.organizer_id = organizer_id
        request.organizer_approved = organizer_approved
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

    @staticmethod
    def resolve_organizer_context(request: Any) -> tuple[Any, bool]:
        """
        Resolve organizer identity and approval state in the owning context.

        One query retrieves both values so approval context does not add a
        second database round trip.
        """
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None, False

        row = Organizer.objects.filter(user_id=user.pk).values_list("pk", "validation_status").first()
        if row is None:
            return None, False

        organizer_id, validation_status = row
        return organizer_id, validation_status == ORGANIZER_APPROVED

    @staticmethod
    def resolve_organizer_id(request: Any) -> Any:
        """Compatibility helper returning only the resolved organizer identifier."""
        organizer_id, _ = OrganizerScopedMixin.resolve_organizer_context(request)
        return organizer_id


# ---------------------------------------------------------------------------
# Organizer application and current dossier
# ---------------------------------------------------------------------------


class OrganizerApplyView(APIView):
    """POST /api/v1/organizers/apply."""

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.ORGANIZER_CREATE

    @extend_schema(
        operation_id="organizers_apply",
        summary="Deposer une candidature organisateur",
        request=OrganizerApplySerializer,
        responses={
            201: OrganizerSerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = OrganizerApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if Organizer.objects.filter(user_id=request.user.pk).exists():
            raise ConflictError(
                code="ORGANIZER_ALREADY_EXISTS",
                message="Un dossier organisateur existe déjà pour ce compte.",
            )

        data = organizer_apply_data(serializer.validated_data)
        proposed_rate = serializer.validated_data["proposed_commission_rate"]

        try:
            with transaction.atomic():
                organizer = Organizer.objects.create(
                    user_id=request.user.pk,
                    **data,
                )

                OrganizerCommissionService.create_initial_proposal(
                    organizer_id=organizer.pk,
                    actor_id=request.user.pk,
                    rate=proposed_rate,
                )

                grant_organizer_role(
                    user_id=request.user.pk,
                )
        except IntegrityError as exc:
            raise ConflictError(
                code="ORGANIZER_ALREADY_EXISTS",
                message="Un dossier organisateur existe déjà.",
            ) from exc

        response = Response(
            OrganizerSerializer(organizer).data,
            status=status.HTTP_201_CREATED,
        )
        response["ETag"] = format_etag(organizer.version)
        return response


class OrganizerMeView(OrganizerScopedMixin, APIView):
    """GET /api/v1/organizers/me."""

    permission_classes = [IsAuthenticated, OrganizerRecordPermission]
    required_action = Action.ORGANIZER_READ

    @extend_schema(
        operation_id="organizers_me_get",
        summary="Lire le dossier organisateur courant",
        responses={
            200: OrganizerSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(self, request: Request) -> Response:
        organizer = Organizer.objects.filter(user_id=request.user.pk).first()

        if organizer is None:
            from apps.core.exceptions import NotFoundBusinessError

            raise NotFoundBusinessError()

        self.check_object_permissions(request, organizer)

        response = Response(
            OrganizerSerializer(organizer).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(organizer.version)
        return response


# ---------------------------------------------------------------------------
# Negociation de commission - Organizer
# ---------------------------------------------------------------------------


def _commission_response(
    organizer: Organizer,
) -> Response:
    response = Response(
        OrganizerCommissionNegotiationSerializer(
            organizer_commission_negotiation_data(
                organizer,
            ),
        ).data,
        status=status.HTTP_200_OK,
    )
    response["ETag"] = format_etag(organizer.version)
    return response


def _current_organizer(
    request: Request,
) -> Organizer:
    organizer = Organizer.objects.filter(
        user_id=request.user.pk,
    ).first()

    if organizer is None:
        from apps.core.exceptions import NotFoundBusinessError

        raise NotFoundBusinessError()

    return organizer


class OrganizerCommissionNegotiationView(
    OrganizerScopedMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        OrganizerRecordPermission,
    ]
    required_action = Action.ORGANIZER_READ

    @extend_schema(
        operation_id="organizers_commission_negotiation_get",
        summary="Lire la negociation de commission",
        responses={
            200: OrganizerCommissionNegotiationSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        organizer = _current_organizer(request)
        self.check_object_permissions(
            request,
            organizer,
        )
        return _commission_response(organizer)


class OrganizerCommissionProposalView(
    OrganizerScopedMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        OrganizerRecordPermission,
    ]
    required_action = Action.ORGANIZER_UPDATE

    @extend_schema(
        operation_id="organizers_commission_proposal_create",
        summary="Faire une contre-proposition de commission",
        request=OrganizerCommissionProposalCreateSerializer,
        responses={
            200: OrganizerCommissionNegotiationSerializer,
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
    ) -> Response:
        organizer = _current_organizer(request)
        self.check_object_permissions(
            request,
            organizer,
        )

        serializer = OrganizerCommissionProposalCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        organizer = OrganizerCommissionService.organizer_counter(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=parse_if_match(
                request.headers.get("If-Match"),
            ),
            rate=serializer.validated_data["commission_rate"],
        )

        return _commission_response(organizer)


class OrganizerCommissionAcceptView(
    OrganizerScopedMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        OrganizerRecordPermission,
    ]
    required_action = Action.ORGANIZER_UPDATE

    @extend_schema(
        operation_id="organizers_commission_accept",
        summary="Accepter la proposition Admin",
        request=None,
        responses={
            200: OrganizerCommissionNegotiationSerializer,
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
    ) -> Response:
        organizer = _current_organizer(request)
        self.check_object_permissions(
            request,
            organizer,
        )

        organizer = OrganizerCommissionService.organizer_accept(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=parse_if_match(
                request.headers.get("If-Match"),
            ),
        )

        return _commission_response(organizer)


# ---------------------------------------------------------------------------
# S1-A.8b — decisions administratives
# ---------------------------------------------------------------------------


class OrganizerAdminActionView(APIView):
    """
    Socle commun aux decisions administratives.

    L autorisation reste rendue par `identity`. Cette classe ne fait que
    charger la ressource avant `check_object_permissions`, parser la version
    attendue et construire la reponse HTTP versionnee.
    """

    permission_classes = [IsAuthenticated, OrganizerRecordPermission]

    def get_organizer(self, request: Request, organizer_id: Any) -> Organizer:
        organizer = Organizer.objects.filter(pk=organizer_id).first()

        if organizer is None:
            from apps.core.exceptions import NotFoundBusinessError

            raise NotFoundBusinessError()

        self.check_object_permissions(request, organizer)
        return organizer

    @staticmethod
    def expected_version(request: Request) -> int:
        return parse_if_match(request.headers.get("If-Match"))

    @staticmethod
    def response_for(organizer: Organizer) -> Response:
        response = Response(
            OrganizerSerializer(organizer).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(organizer.version)
        return response


class AdminOrganizerCommissionNegotiationView(
    OrganizerAdminActionView,
):
    required_action = Action.ORGANIZER_READ

    @extend_schema(
        operation_id="admin_organizers_commission_negotiation_get",
        summary="Lire la negociation de commission",
        responses={
            200: OrganizerCommissionNegotiationSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
        organizer_id: Any,
    ) -> Response:
        organizer = self.get_organizer(
            request,
            organizer_id,
        )

        return _commission_response(
            organizer,
        )


class AdminOrganizerCommissionProposalView(
    OrganizerAdminActionView,
):
    required_action = Action.ORGANIZER_APPROVE

    @extend_schema(
        operation_id="admin_organizers_commission_proposal_create",
        summary="Faire une contre-proposition de commission",
        request=OrganizerCommissionProposalCreateSerializer,
        responses={
            200: OrganizerCommissionNegotiationSerializer,
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
        organizer_id: Any,
    ) -> Response:
        organizer = self.get_organizer(
            request,
            organizer_id,
        )

        serializer = OrganizerCommissionProposalCreateSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        organizer = OrganizerCommissionService.admin_counter(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=self.expected_version(request),
            rate=serializer.validated_data["commission_rate"],
        )

        return _commission_response(organizer)


class AdminOrganizerCommissionAcceptView(
    OrganizerAdminActionView,
):
    required_action = Action.ORGANIZER_APPROVE

    @extend_schema(
        operation_id="admin_organizers_commission_accept",
        summary="Accepter la proposition Organizer",
        request=None,
        responses={
            200: OrganizerCommissionNegotiationSerializer,
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
        organizer_id: Any,
    ) -> Response:
        organizer = self.get_organizer(
            request,
            organizer_id,
        )

        organizer = OrganizerCommissionService.admin_accept(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=self.expected_version(request),
        )

        return _commission_response(organizer)


class OrganizerApproveView(OrganizerAdminActionView):
    """POST /api/v1/admin/organizers/{id}/approve."""

    required_action = Action.ORGANIZER_APPROVE

    @extend_schema(
        operation_id="admin_organizers_approve",
        summary="Approuver un dossier organisateur",
        request=None,
        responses={
            200: OrganizerSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            428: ERROR_RESPONSE,
        },
    )
    def post(self, request: Request, organizer_id: Any) -> Response:
        organizer = self.get_organizer(request, organizer_id)
        expected_version = self.expected_version(request)

        organizer = OrganizerOnboardingService.approve(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=expected_version,
        )
        return self.response_for(organizer)


class OrganizerRejectView(OrganizerAdminActionView):
    """POST /api/v1/admin/organizers/{id}/reject."""

    required_action = Action.ORGANIZER_REJECT

    @extend_schema(
        operation_id="admin_organizers_reject",
        summary="Rejeter un dossier organisateur",
        request=OrganizerRejectSerializer,
        responses={
            200: OrganizerSerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            428: ERROR_RESPONSE,
        },
    )
    def post(self, request: Request, organizer_id: Any) -> Response:
        organizer = self.get_organizer(request, organizer_id)

        serializer = OrganizerRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expected_version = self.expected_version(request)

        organizer = OrganizerOnboardingService.reject(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=expected_version,
            reason=serializer.validated_data["reason"],
        )
        return self.response_for(organizer)


class OrganizerSuspendView(OrganizerAdminActionView):
    """POST /api/v1/admin/organizers/{id}/suspend."""

    required_action = Action.ORGANIZER_SUSPEND

    @extend_schema(
        operation_id="admin_organizers_suspend",
        summary="Suspendre un dossier organisateur",
        request=None,
        responses={
            200: OrganizerSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            428: ERROR_RESPONSE,
        },
    )
    def post(self, request: Request, organizer_id: Any) -> Response:
        organizer = self.get_organizer(request, organizer_id)
        expected_version = self.expected_version(request)

        organizer = OrganizerOnboardingService.suspend(
            organizer_id=organizer.pk,
            actor_id=request.user.pk,
            expected_version=expected_version,
        )
        return self.response_for(organizer)


# ---------------------------------------------------------------------------
# Administration detail
# ---------------------------------------------------------------------------


class AdminOrganizerDetailView(APIView):
    """
    GET /api/v1/admin/organizers/{id}.

    This endpoint is strictly administrative. A second object-level check with
    an empty resource forces fail-closed behavior for owner-scoped roles.
    """

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.ORGANIZER_READ

    @extend_schema(
        operation_id="admin_organizers_retrieve",
        summary="Consulter un dossier organisateur",
        responses={
            200: OrganizerSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(self, request: Request, organizer_id: Any) -> Response:
        permission = ActionPermission()

        if not permission.has_object_permission(request, self, object()):
            self.permission_denied(
                request,
                message=permission.message,
                code=permission.code,
            )

        organizer = Organizer.objects.filter(pk=organizer_id).first()
        if organizer is None:
            from apps.core.exceptions import NotFoundBusinessError

            raise NotFoundBusinessError()

        response = Response(
            OrganizerSerializer(organizer).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(organizer.version)
        return response


# ---------------------------------------------------------------------------
# Administration list
# ---------------------------------------------------------------------------


class AdminOrganizerListView(APIView):
    """
    GET /api/v1/admin/organizers/.

    List endpoints need an explicit second permission check because DRF does not
    call `has_object_permission()` for every queryset item. An empty resource is
    deliberate: unrestricted admin scope passes while owner scopes fail closed.
    """

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.ORGANIZER_READ

    @extend_schema(
        operation_id="admin_organizers_list",
        summary="Lister les dossiers organisateurs",
        responses={
            200: AdminOrganizerListResponseSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(self, request: Request) -> Response:
        permission = ActionPermission()

        if not permission.has_object_permission(request, self, object()):
            self.permission_denied(
                request,
                message=permission.message,
                code=permission.code,
            )

        queryset = Organizer.objects.all().order_by("created_at", "pk")

        validation_status = request.query_params.get("validation_status")
        if validation_status:
            queryset = queryset.filter(validation_status=validation_status)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)

        serializer = OrganizerSerializer(page, many=True)

        pending_reactivations = (
            OrganizerReactivationRequest.objects.filter(
                status=OrganizerReactivationRequest.STATUS_PENDING,
            )
            .select_related("organizer")
            .order_by("-created_at", "-pk")
        )

        pending_count = pending_reactivations.count()
        pending_items = pending_reactivations[:5]

        response = paginator.get_paginated_response(serializer.data)
        response.data["pending_reactivation_count"] = pending_count
        response.data["pending_reactivations"] = AdminOrganizerPendingReactivationSerializer(
            pending_items,
            many=True,
        ).data
        return response
