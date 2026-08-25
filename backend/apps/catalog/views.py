from __future__ import annotations

from typing import Any

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.concurrency import (
    format_etag,
    parse_if_match,
    versioned_update,
)
from apps.core.exceptions import (
    ConflictError,
    NotFoundBusinessError,
)
from apps.core.openapi import ERROR_RESPONSE
from apps.core.pagination import StandardPagination
from apps.identity.api import (
    Action,
    ActionPermission,
    IsApprovedOrganizer,
)
from apps.organizing.api import resolve_organizer_context

from .models import Category, Event
from .permissions import (
    EventCollectionPermission,
    EventResourcePermission,
)
from .serializers import (
    CategorySerializer,
    EventSerializer,
    EventWriteSerializer,
)


class CatalogOrganizerContextMixin:
    """
    Enrichit la requête AVANT les permissions.

    Le contexte organizing reste responsable de résoudre son propre modèle ;
    catalog ne connaît que son API publique.
    """

    def initial(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        user = getattr(request, "user", None)

        organizer_id = None
        organizer_approved = False

        if (
            user is not None
            and getattr(
                user,
                "is_authenticated",
                False,
            )
        ):
            (
                organizer_id,
                organizer_approved,
            ) = resolve_organizer_context(
                user_id=user.pk,
            )

        request.organizer_id = organizer_id
        request.organizer_approved = organizer_approved

        super().initial(
            request,
            *args,
            **kwargs,
        )


class CategoryListView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        ActionPermission,
    ]

    required_action = Action.CATEGORY_READ

    @extend_schema(
        operation_id="catalog_categories_list",
        summary="Lister les catégories d événement",
        responses={
            200: CategorySerializer(many=True),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        categories = Category.objects.order_by("name")

        return Response(
            CategorySerializer(
                categories,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )


class EventListCreateView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventCollectionPermission,
    ]

    @extend_schema(
        operation_id="catalog_events_list",
        summary="Lister mes événements",
        responses={
            200: EventSerializer(many=True),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        queryset = (
            Event.objects
            .filter(
                organizer_id=request.organizer_id,
            )
            .select_related("category")
            .order_by(
                "-created_at",
                "-id",
            )
        )

        paginator = StandardPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        return paginator.get_paginated_response(
            EventSerializer(
                page,
                many=True,
            ).data
        )

    @extend_schema(
        operation_id="catalog_events_create",
        summary="Créer un événement brouillon",
        request=EventWriteSerializer,
        responses={
            201: EventSerializer,
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
        serializer = EventWriteSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = dict(
            serializer.validated_data
        )

        data.setdefault(
            "description",
            "",
        )

        try:
            event = Event.objects.create(
                organizer_id=request.organizer_id,
                status=Event.DRAFT,
                **data,
            )
        except IntegrityError as exc:
            raise ConflictError(
                code="EVENT_ALREADY_EXISTS",
                message=(
                    "Un événement portant ce nom existe "
                    "déjà pour votre organisation."
                ),
            ) from exc

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )

        response["ETag"] = format_etag(
            event.version
        )

        return response


class EventDetailView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventResourcePermission,
    ]

    def get_object(
        self,
        request: Request,
        event_id: Any,
    ) -> Event:
        # Le filtre propriétaire empêche aussi de révéler l existence
        # d un événement d un autre organisateur.
        event = (
            Event.objects
            .select_related("category")
            .filter(
                pk=event_id,
                organizer_id=request.organizer_id,
            )
            .first()
        )

        if event is None:
            raise NotFoundBusinessError()

        self.check_object_permissions(
            request,
            event,
        )

        return event

    @extend_schema(
        operation_id="catalog_events_retrieve",
        summary="Consulter un de mes événements",
        responses={
            200: EventSerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        event = self.get_object(
            request,
            event_id,
        )

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            event.version
        )

        return response

    @extend_schema(
        operation_id="catalog_events_update",
        summary="Modifier un de mes événements",
        request=EventWriteSerializer,
        responses={
            200: EventSerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
            428: ERROR_RESPONSE,
        },
    )
    def patch(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        event = self.get_object(
            request,
            event_id,
        )

        serializer = EventWriteSerializer(
            data=request.data,
            partial=True,
            context={
                "event": event,
            },
        )

        serializer.is_valid(
            raise_exception=True,
        )

        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        updates = dict(
            serializer.validated_data
        )

        category = updates.pop(
            "category",
            None,
        )

        if category is not None:
            updates["category_id"] = category.pk

        try:
            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates=updates,
            )
        except IntegrityError as exc:
            raise ConflictError(
                code="EVENT_ALREADY_EXISTS",
                message=(
                    "Un événement portant ce nom existe "
                    "déjà pour votre organisation."
                ),
            ) from exc

        event.refresh_from_db()

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response
