"""
Socle de vues du contexte `organizing`.

**Aucune route n est exposee au lot S1-A.8a.** Ce module ne contient que le
mixin qui rend la portee `OWN_ORGANIZER` utilisable ; les six points de
terminaison du plan §3.3 arrivent au lot S1-A.8b.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.concurrency import format_etag, parse_if_match
from apps.core.exceptions import ConflictError
from apps.core.pagination import StandardPagination
from apps.identity.api import Action, ActionPermission, grant_organizer_role

from .models import Organizer
from .permissions import OrganizerRecordPermission
from .serializers import (
    OrganizerApplySerializer,
    OrganizerRejectSerializer,
    OrganizerSerializer,
    organizer_apply_data,
)
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
        request.organizer_id = self.resolve_organizer_id(request)
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

    @staticmethod
    def resolve_organizer_id(request: Any) -> Any:
        """
        Une requete, dans le contexte proprietaire de la donnee.

        Le cout ne tombe QUE sur les routes de ce contexte, et jamais sur le
        chemin chaud d `identity` — dont l invariant « aucune requete SQL par
        controle d autorisation » reste prouve par `django_assert_num_queries(0)`.
        """
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return None
        return Organizer.objects.filter(user_id=user.pk).values_list("pk", flat=True).first()


# ---------------------------------------------------------------------------
# S1-A.8b — candidature et dossier courant
# ---------------------------------------------------------------------------

class OrganizerApplyView(APIView):
    """POST /api/v1/organizers/apply."""

    permission_classes = [IsAuthenticated, ActionPermission]
    required_action = Action.ORGANIZER_CREATE

    def post(self, request: Request) -> Response:
        serializer = OrganizerApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if Organizer.objects.filter(user_id=request.user.pk).exists():
            raise ConflictError(
                code="ORGANIZER_ALREADY_EXISTS",
                message="Un dossier organisateur existe déjà pour ce compte.",
            )

        data = organizer_apply_data(serializer.validated_data)

        try:
            organizer = Organizer.objects.create(
                user_id=request.user.pk,
                **data,
            )
        except IntegrityError as exc:
            raise ConflictError(
                code="ORGANIZER_ALREADY_EXISTS",
                message="Un dossier organisateur existe déjà.",
            ) from exc

        grant_organizer_role(user_id=request.user.pk)

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
