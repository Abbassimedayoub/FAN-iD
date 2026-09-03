"""
Socle de vues du contexte `organizing`.

**Aucune route n est exposee au lot S1-A.8a.** Ce module ne contient que le
mixin qui rend la portee `OWN_ORGANIZER` utilisable ; les six points de
terminaison du plan §3.3 arrivent au lot S1-A.8b.
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
from .models import Organizer
from .permissions import OrganizerRecordPermission
from .serializers import (
    AdminOrganizerListResponseSerializer,
    OrganizerApplySerializer,
    OrganizerRejectSerializer,
    OrganizerSerializer,
    organizer_apply_data,
)
from .services.commissions import OrganizerCommissionService
from .services.onboarding import OrganizerOnboardingService


class OrganizerScopedMixin:
    """
    Pose `request.organizer_id` AVANT que DRF ne controle les permissions.

    ## Pourquoi ici, et pas dans `identity`

    `identity` ignore qu `organizing` existe (ADR-S1-05) : c est le sens de
    dependance qui suit le domaine, un compte existant sans organisateur et
    jamais l inverse. `subject_from_request` lit donc un PRIMITIF pose sur la
    requete, exactement comme il lit deja `request.auth_level`.

    ## Pourquoi dans `initial()`

    DRF appelle `initial()` puis, a l interieur, `perform_authentication()` et
    `check_permissions()`. Poser l attribut plus tard — dans `get_object()` ou
    le corps de la vue — arriverait APRES le premier controle de permission.

    Toucher `request.user` ici declenche l authentification : c est exactement
    ce que fait `perform_authentication()` la ligne suivante, donc ni un effet
    de bord ni un cout supplementaire.

    ## Ce qui se passe si on l oublie

    `subject.organizer_id` reste `None`, et `engine._check_scope` refuse avec
    `RESOURCE_ATTRIBUTE_MISSING`. **Le refus vient du moteur, pas d une
    convention** — c est ce qui rend l option B de l ADR sure plutot que
    seulement propre, et un test le fige.
    """

    def initial(self, request: Any, *args: Any, **kwargs: Any) -> None:
        organizer_id, organizer_approved = self.resolve_organizer_context(request)
        request.organizer_id = organizer_id
        request.organizer_approved = organizer_approved
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

    @staticmethod
    def resolve_organizer_context(request: Any) -> tuple[Any, bool]:
        """
        Une requete, dans le contexte proprietaire de la donnee.

        Le meme SELECT charge l identifiant et le statut : ajouter le primitif
        d approbation ne doit pas ajouter une seconde requete SQL.
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
        """Compatibilite : ne renvoie que l identifiant du contexte resolu."""
        organizer_id, _ = OrganizerScopedMixin.resolve_organizer_context(request)
        return organizer_id


# ---------------------------------------------------------------------------
# S1-A.8b — candidature et dossier courant
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
        proposed_rate = serializer.validated_data[
            "proposed_commission_rate"
        ]

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
# S1-B — detail d administration
# ---------------------------------------------------------------------------


class AdminOrganizerDetailView(APIView):
    """
    GET /api/v1/admin/organizers/{id}.

    Cette surface est strictement administrative. `ORGANIZER_READ` existe aussi
    en `OWN_ORGANIZER` pour d autres roles ; comme pour la liste admin, un
    second controle sur une ressource vide exige donc implicitement `Scope.ANY`
    et refuse fail-closed les portees proprietaires.
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
# S1-A.8b — liste d administration
# ---------------------------------------------------------------------------


class AdminOrganizerListView(APIView):
    """
    GET /api/v1/admin/organizers/.

    Le second controle explicite est indispensable pour une liste : DRF
    n appelle jamais has_object_permission() sur les elements d un queryset.

    Resource() vide est volontaire :
    - ADMIN / Scope.ANY passe ;
    - ORGANIZER ou SCANNER / Scope.OWN_ORGANIZER echoue fail-closed.
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
        return paginator.get_paginated_response(serializer.data)
