from __future__ import annotations

import logging
import mimetypes
import uuid
from typing import Any

from django.core import signing
from django.db import (
    IntegrityError,
    transaction,
)
from django.db.models import Sum
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.adapters.storage import (
    LocalStorage,
    build_object_storage,
    resolve_local_presigned_key,
)
from apps.core.concurrency import (
    format_etag,
    parse_if_match,
    versioned_update,
)
from apps.core.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundBusinessError,
)
from apps.core.openapi import ERROR_RESPONSE
from apps.core.pagination import StandardPagination
from apps.core.outbox.publisher import publish_event
from apps.identity.api import (
    Action,
    ActionPermission,
    IsApprovedOrganizer,
)
from apps.organizing.api import (
    resolve_organizer_context,
)

from .events import (
    AGGREGATE_EVENT,
    CATALOG_EVENT_PUBLISHED,
    event_status_payload,
)
from .models import (
    Category,
    Event,
    TicketCategory,
)
from .permissions import (
    EventArchivePermission,
    EventCollectionPermission,
    EventImagePermission,
    EventPublishPermission,
    EventResourcePermission,
    TicketCategoryCollectionPermission,
    TicketCategoryResourcePermission,
)
from .serializers import (
    CategorySerializer,
    EventSerializer,
    EventWriteSerializer,
    TicketCategorySerializer,
    TicketCategoryWriteSerializer,
)


logger = logging.getLogger("fanid.catalog")

EVENT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
EVENT_IMAGE_URL_TTL_SECONDS = 300

EVENT_IMAGE_TYPES = {
    "image/jpeg": {
        "extension": "jpg",
        "magic": (
            b"\xff\xd8\xff",
        ),
    },
    "image/png": {
        "extension": "png",
        "magic": (
            b"\x89PNG\r\n\x1a\n",
        ),
    },
}


def _require_draft(event: Event) -> None:
    if event.status != Event.DRAFT:
        raise ConflictError(
            code="EVENT_NOT_DRAFT",
            message=(
                "Cette opération n est autorisée "
                "que sur un événement brouillon."
            ),
        )


def _require_published_for_archive(
    event: Event,
) -> None:
    if event.status != Event.PUBLISHED:
        raise InvalidStateTransitionError(
            details={
                "current_state": event.status,
                "target_state": Event.ARCHIVED,
            }
        )


def _ticket_quota_total(
    event: Event,
    *,
    exclude_id: Any = None,
) -> int:
    queryset = TicketCategory.objects.filter(
        event=event,
    )

    if exclude_id is not None:
        queryset = queryset.exclude(
            pk=exclude_id,
        )

    value = queryset.aggregate(
        total=Sum("quota")
    )["total"]

    return int(value or 0)


def _validate_quota_capacity(
    *,
    event: Event,
    quota_total: int,
) -> None:
    if event.capacity_total is None:
        raise ValidationError(
            {
                "capacity_total": (
                    "Définissez la capacité totale "
                    "avant les catégories de billets."
                )
            }
        )

    if quota_total > event.capacity_total:
        raise ValidationError(
            {
                "quota": (
                    "La somme des quotas dépasse "
                    "la capacité totale de l événement."
                )
            }
        )


def _validate_event_image(
    uploaded_file: Any,
) -> str:
    if uploaded_file is None:
        raise ValidationError(
            {
                "image": (
                    "Le fichier image est requis."
                )
            }
        )

    size = int(
        getattr(
            uploaded_file,
            "size",
            0,
        )
        or 0
    )

    if size <= 0:
        raise ValidationError(
            {
                "image": (
                    "Le fichier image est vide."
                )
            }
        )

    if size > EVENT_IMAGE_MAX_BYTES:
        raise ValidationError(
            {
                "image": (
                    "Le visuel ne doit pas "
                    "dépasser 5 Mo."
                )
            }
        )

    declared_type = str(
        getattr(
            uploaded_file,
            "content_type",
            "",
        )
        or ""
    ).split(
        ";",
        1,
    )[0].strip().lower()

    expected = EVENT_IMAGE_TYPES.get(
        declared_type
    )

    if expected is None:
        raise ValidationError(
            {
                "image": (
                    "Formats autorisés : "
                    "PNG et JPEG."
                )
            }
        )

    header = uploaded_file.read(16)
    uploaded_file.seek(0)

    if not any(
        header.startswith(prefix)
        for prefix in expected["magic"]
    ):
        raise ValidationError(
            {
                "image": (
                    "Le contenu du fichier ne "
                    "correspond pas à son type."
                )
            }
        )

    return str(expected["extension"])


def _safe_storage_delete(
    storage: Any,
    key: str,
) -> None:
    if not key:
        return

    try:
        storage.delete(key)
    except Exception:
        logger.exception(
            "event_image_cleanup_failed",
            extra={
                "storage_key": key,
            },
        )


class CatalogOrganizerContextMixin:
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
        request.organizer_approved = (
            organizer_approved
        )

        super().initial(
            request,
            *args,
            **kwargs,
        )

    def get_owned_event(
        self,
        request: Request,
        event_id: Any,
        *,
        for_update: bool = False,
    ) -> Event:
        queryset = (
            Event.objects
            .select_related("category")
            .filter(
                pk=event_id,
                organizer_id=request.organizer_id,
            )
        )

        if for_update:
            queryset = queryset.select_for_update()

        event = queryset.first()

        if event is None:
            raise NotFoundBusinessError()

        return event


class LocalStorageMediaView(APIView):
    """
    Lecture d un objet local via URL signée.

    En production S3 fournit directement son URL présignée.
    """

    authentication_classes = []
    permission_classes = []

    def get(
        self,
        request: Request,
        token: str,
    ) -> FileResponse:
        try:
            key = resolve_local_presigned_key(
                token
            )
        except (
            signing.BadSignature,
            signing.SignatureExpired,
        ) as exc:
            raise NotFoundBusinessError(
                code="STORAGE_OBJECT_NOT_FOUND",
                message="Objet introuvable.",
            ) from exc

        storage = build_object_storage()

        if not isinstance(
            storage,
            LocalStorage,
        ):
            raise NotFoundBusinessError(
                code="STORAGE_OBJECT_NOT_FOUND",
                message="Objet introuvable.",
            )

        try:
            path = storage.path_for_key(key)
        except ValueError as exc:
            raise NotFoundBusinessError(
                code="STORAGE_OBJECT_NOT_FOUND",
                message="Objet introuvable.",
            ) from exc

        if not path.is_file():
            raise NotFoundBusinessError(
                code="STORAGE_OBJECT_NOT_FOUND",
                message="Objet introuvable.",
            )

        content_type = (
            mimetypes.guess_type(key)[0]
            or "application/octet-stream"
        )

        return FileResponse(
            path.open("rb"),
            content_type=content_type,
        )


class EventImageView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventImagePermission,
    ]

    parser_classes = [
        MultiPartParser,
        FormParser,
    ]

    def get_object(
        self,
        request: Request,
        event_id: Any,
        *,
        for_update: bool = False,
    ) -> Event:
        event = self.get_owned_event(
            request,
            event_id,
            for_update=for_update,
        )

        self.check_object_permissions(
            request,
            event,
        )

        return event

    def get(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        event = self.get_object(
            request,
            event_id,
        )

        if not event.image_key:
            raise NotFoundBusinessError(
                code="EVENT_IMAGE_NOT_FOUND",
                message=(
                    "Aucun visuel n est associé "
                    "à cet événement."
                ),
            )

        storage = build_object_storage()

        try:
            url = storage.presigned_url(
                event.image_key,
                EVENT_IMAGE_URL_TTL_SECONDS,
            )
        except KeyError as exc:
            raise NotFoundBusinessError(
                code="EVENT_IMAGE_NOT_FOUND",
                message=(
                    "Le visuel de cet événement "
                    "est introuvable."
                ),
            ) from exc

        response = Response(
            {
                "url": url,
                "expires_in": (
                    EVENT_IMAGE_URL_TTL_SECONDS
                ),
                "version": event.version,
            },
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            event.version
        )

        return response

    def put(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        initial_event = self.get_object(
            request,
            event_id,
        )

        _require_draft(initial_event)

        uploaded_file = request.FILES.get(
            "image"
        )

        extension = _validate_event_image(
            uploaded_file
        )

        storage = build_object_storage()

        new_key = (
            "events/"
            f"{initial_event.organizer_id}/"
            f"{initial_event.pk}/"
            f"{uuid.uuid4().hex}."
            f"{extension}"
        )

        storage.upload(
            uploaded_file,
            new_key,
        )

        try:
            with transaction.atomic():
                event = self.get_object(
                    request,
                    event_id,
                    for_update=True,
                )

                _require_draft(event)

                old_key = event.image_key

                new_version = versioned_update(
                    model=Event,
                    pk=event.pk,
                    expected_version=(
                        expected_version
                    ),
                    updates={
                        "image_key": new_key,
                    },
                )

                event.refresh_from_db()

                if (
                    old_key
                    and old_key != new_key
                ):
                    transaction.on_commit(
                        lambda key=old_key: (
                            _safe_storage_delete(
                                storage,
                                key,
                            )
                        )
                    )

        except Exception:
            _safe_storage_delete(
                storage,
                new_key,
            )
            raise

        response = Response(
            EventSerializer(
                event,
                context={
                    "storage": storage,
                },
            ).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response

    def delete(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        with transaction.atomic():
            event = self.get_object(
                request,
                event_id,
                for_update=True,
            )

            _require_draft(event)

            old_key = event.image_key

            if not old_key:
                raise NotFoundBusinessError(
                    code="EVENT_IMAGE_NOT_FOUND",
                    message=(
                        "Aucun visuel n est associé "
                        "à cet événement."
                    ),
                )

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates={
                    "image_key": "",
                },
            )

            transaction.on_commit(
                lambda key=old_key: (
                    _safe_storage_delete(
                        storage=build_object_storage(),
                        key=key,
                    )
                )
            )

        response = Response(
            status=status.HTTP_204_NO_CONTENT,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response


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
        categories = Category.objects.order_by(
            "name"
        )

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
        data.setdefault(
            "venue",
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
        *,
        for_update: bool = False,
    ) -> Event:
        event = self.get_owned_event(
            request,
            event_id,
            for_update=for_update,
        )

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
        summary="Modifier un événement brouillon",
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
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        try:
            with transaction.atomic():
                event = self.get_object(
                    request,
                    event_id,
                    for_update=True,
                )

                _require_draft(event)

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

                updates = dict(
                    serializer.validated_data
                )

                category = updates.pop(
                    "category",
                    None,
                )

                if category is not None:
                    updates[
                        "category_id"
                    ] = category.pk

                if "capacity_total" in updates:
                    quota_total = (
                        _ticket_quota_total(event)
                    )

                    capacity = updates[
                        "capacity_total"
                    ]

                    if (
                        quota_total > 0
                        and capacity is None
                    ):
                        raise ValidationError(
                            {
                                "capacity_total": (
                                    "La capacité ne peut pas "
                                    "être supprimée tant que "
                                    "des quotas existent."
                                )
                            }
                        )

                    if (
                        capacity is not None
                        and quota_total > capacity
                    ):
                        raise ValidationError(
                            {
                                "capacity_total": (
                                    "La capacité totale ne "
                                    "peut pas être inférieure "
                                    "à la somme des quotas."
                                )
                            }
                        )

                new_version = versioned_update(
                    model=Event,
                    pk=event.pk,
                    expected_version=(
                        expected_version
                    ),
                    updates=updates,
                )

                event.refresh_from_db()

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
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response


class EventPublishView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventPublishPermission,
    ]

    @extend_schema(
        operation_id="catalog_events_publish",
        summary="Publier un événement brouillon",
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
    def post(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        with transaction.atomic():
            event = self.get_owned_event(
                request,
                event_id,
                for_update=True,
            )

            self.check_object_permissions(
                request,
                event,
            )

            _require_draft(event)

            errors = {}

            if not event.venue.strip():
                errors["venue"] = (
                    "Le lieu est requis avant publication."
                )

            if event.capacity_total is None:
                errors["capacity_total"] = (
                    "La capacité totale est requise "
                    "avant publication."
                )

            categories = (
                TicketCategory.objects
                .filter(event=event)
            )

            category_count = categories.count()

            quota_total = int(
                categories.aggregate(
                    total=Sum("quota")
                )["total"]
                or 0
            )

            if category_count == 0:
                errors["ticket_categories"] = (
                    "Ajoutez au moins une catégorie "
                    "de billets avant publication."
                )

            if (
                event.capacity_total is not None
                and quota_total
                > event.capacity_total
            ):
                errors["quota"] = (
                    "La somme des quotas dépasse "
                    "la capacité totale."
                )

            if errors:
                raise ValidationError(errors)

            published_at = timezone.now()

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates={
                    "status": Event.PUBLISHED,
                    "published_at": published_at,
                },
            )

            event.refresh_from_db()

            publish_event(
                event_type=CATALOG_EVENT_PUBLISHED,
                aggregate_type=AGGREGATE_EVENT,
                aggregate_id=event.pk,
                actor_id=request.user.pk,
                payload=event_status_payload(
                    status=Event.PUBLISHED,
                ),
            )

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response


class EventArchiveView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventArchivePermission,
    ]

    @extend_schema(
        operation_id="catalog_events_archive",
        summary="Archiver un événement publié",
        responses={
            200: EventSerializer,
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
        event_id: Any,
    ) -> Response:
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        with transaction.atomic():
            event = self.get_owned_event(
                request,
                event_id,
                for_update=True,
            )

            self.check_object_permissions(
                request,
                event,
            )

            _require_published_for_archive(
                event
            )

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates={
                    "status": Event.ARCHIVED,
                },
            )

            event.refresh_from_db()

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response


class TicketCategoryListCreateView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        TicketCategoryCollectionPermission,
    ]

    @extend_schema(
        operation_id=(
            "catalog_ticket_categories_list"
        ),
        summary=(
            "Lister les catégories de billets "
            "d un événement"
        ),
        responses={
            200: TicketCategorySerializer(
                many=True
            ),
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
        event = self.get_owned_event(
            request,
            event_id,
        )

        queryset = (
            TicketCategory.objects
            .filter(event=event)
            .order_by(
                "created_at",
                "id",
            )
        )

        return Response(
            TicketCategorySerializer(
                queryset,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id=(
            "catalog_ticket_categories_create"
        ),
        summary="Créer une catégorie de billets",
        request=TicketCategoryWriteSerializer,
        responses={
            201: TicketCategorySerializer,
            400: ERROR_RESPONSE,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
        },
    )
    def post(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        serializer = (
            TicketCategoryWriteSerializer(
                data=request.data,
            )
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = dict(
            serializer.validated_data
        )

        try:
            with transaction.atomic():
                event = self.get_owned_event(
                    request,
                    event_id,
                    for_update=True,
                )

                _require_draft(event)

                quota_total = (
                    _ticket_quota_total(event)
                    + data["quota"]
                )

                _validate_quota_capacity(
                    event=event,
                    quota_total=quota_total,
                )

                category = (
                    TicketCategory.objects.create(
                        event=event,
                        **data,
                    )
                )

        except IntegrityError as exc:
            raise ConflictError(
                code=(
                    "TICKET_CATEGORY_ALREADY_EXISTS"
                ),
                message=(
                    "Une catégorie portant ce nom "
                    "existe déjà pour cet événement."
                ),
            ) from exc

        response = Response(
            TicketCategorySerializer(
                category
            ).data,
            status=status.HTTP_201_CREATED,
        )

        response["ETag"] = format_etag(
            category.version
        )

        return response


class TicketCategoryDetailView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        TicketCategoryResourcePermission,
    ]

    def get_object(
        self,
        request: Request,
        *,
        event: Event,
        ticket_category_id: Any,
        for_update: bool = False,
    ) -> TicketCategory:
        queryset = (
            TicketCategory.objects
            .select_related("event")
            .filter(
                pk=ticket_category_id,
                event=event,
            )
        )

        if for_update:
            queryset = queryset.select_for_update()

        category = queryset.first()

        if category is None:
            raise NotFoundBusinessError()

        self.check_object_permissions(
            request,
            category,
        )

        return category

    @extend_schema(
        operation_id=(
            "catalog_ticket_categories_retrieve"
        ),
        summary="Consulter une catégorie de billets",
        responses={
            200: TicketCategorySerializer,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
        event_id: Any,
        ticket_category_id: Any,
    ) -> Response:
        event = self.get_owned_event(
            request,
            event_id,
        )

        category = self.get_object(
            request,
            event=event,
            ticket_category_id=(
                ticket_category_id
            ),
        )

        response = Response(
            TicketCategorySerializer(
                category
            ).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            category.version
        )

        return response

    @extend_schema(
        operation_id=(
            "catalog_ticket_categories_update"
        ),
        summary="Modifier une catégorie de billets",
        request=TicketCategoryWriteSerializer,
        responses={
            200: TicketCategorySerializer,
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
        ticket_category_id: Any,
    ) -> Response:
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        try:
            with transaction.atomic():
                event = self.get_owned_event(
                    request,
                    event_id,
                    for_update=True,
                )

                _require_draft(event)

                category = self.get_object(
                    request,
                    event=event,
                    ticket_category_id=(
                        ticket_category_id
                    ),
                    for_update=True,
                )

                serializer = (
                    TicketCategoryWriteSerializer(
                        data=request.data,
                        partial=True,
                        context={
                            "ticket_category": category,
                        },
                    )
                )

                serializer.is_valid(
                    raise_exception=True,
                )

                updates = dict(
                    serializer.validated_data
                )

                quota = updates.get(
                    "quota",
                    category.quota,
                )

                quota_total = (
                    _ticket_quota_total(
                        event,
                        exclude_id=category.pk,
                    )
                    + quota
                )

                _validate_quota_capacity(
                    event=event,
                    quota_total=quota_total,
                )

                new_version = versioned_update(
                    model=TicketCategory,
                    pk=category.pk,
                    expected_version=(
                        expected_version
                    ),
                    updates=updates,
                )

                category.refresh_from_db()

        except IntegrityError as exc:
            raise ConflictError(
                code=(
                    "TICKET_CATEGORY_ALREADY_EXISTS"
                ),
                message=(
                    "Une catégorie portant ce nom "
                    "existe déjà pour cet événement."
                ),
            ) from exc

        response = Response(
            TicketCategorySerializer(
                category
            ).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(
            new_version
        )

        return response

    @extend_schema(
        operation_id=(
            "catalog_ticket_categories_delete"
        ),
        summary="Supprimer une catégorie de billets",
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
        event_id: Any,
        ticket_category_id: Any,
    ) -> Response:
        expected_version = parse_if_match(
            request.headers.get("If-Match")
        )

        with transaction.atomic():
            event = self.get_owned_event(
                request,
                event_id,
                for_update=True,
            )

            _require_draft(event)

            category = self.get_object(
                request,
                event=event,
                ticket_category_id=(
                    ticket_category_id
                ),
                for_update=True,
            )

            if category.sold_count > 0:
                raise ConflictError(
                    code=(
                        "TICKET_CATEGORY_HAS_SALES"
                    ),
                    message=(
                        "Une catégorie ayant déjà "
                        "des ventes ne peut pas être "
                        "supprimée."
                    ),
                )

            versioned_update(
                model=TicketCategory,
                pk=category.pk,
                expected_version=(
                    expected_version
                ),
                updates={},
            )

            category.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )
