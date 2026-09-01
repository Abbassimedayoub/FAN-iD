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
    StaleResourceError,
)
from apps.core.openapi import ERROR_RESPONSE
from apps.core.pagination import StandardPagination
from apps.core.outbox.publisher import publish_event
from apps.identity.api import (
    Action,
    ActionPermission,
    IsApprovedOrganizer,
    Resource,
)
from apps.organizing.api import (
    get_scanner_assignment_summary,
    list_scanner_assignment_summaries,
    resolve_organizer_context,
)

from .events import (
    AGGREGATE_EVENT,
    CATALOG_EVENT_CANCELLED,
    CATALOG_EVENT_POSTPONED,
    CATALOG_EVENT_PUBLISHED,
    CATALOG_EVENT_SUSPENDED,
    event_lifecycle_payload,
    event_status_payload,
)
from .models import (
    Category,
    Event,
    EventScannerAssignment,
    TicketCategory,
)
from .permissions import (
    CategoryCollectionPermission,
    CategoryResourcePermission,
    EventArchivePermission,
    EventUnarchivePermission,
    EventCancelPermission,
    EventCollectionPermission,
    EventImagePermission,
    EventPostponePermission,
    EventPublishPermission,
    EventResourcePermission,
    EventSuspendPermission,
    EventScannerAssignmentPermission,
    TicketCategoryCollectionPermission,
    TicketCategoryResourcePermission,
)
from .serializers import (
    CategoryWriteSerializer,
    CategorySerializer,
    EventCancelSerializer,
    EventPostponeSerializer,
    EventSerializer,
    EventSuspendSerializer,
    EventWriteSerializer,
    EventScannerAssignSerializer,
    EventScannerAssignmentSerializer,
    TicketCategorySerializer,
    TicketCategoryWriteSerializer,
)

logger = logging.getLogger("fanid.catalog")

EVENT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
EVENT_IMAGE_URL_TTL_SECONDS = 300

CATALOG_EVENT_SCANNER_ASSIGNED = "catalog.event.scanner_assigned"

CATALOG_EVENT_SCANNER_UNASSIGNED = "catalog.event.scanner_unassigned"

EVENT_IMAGE_TYPES = {
    "image/jpeg": {
        "extension": "jpg",
        "magic": (b"\xff\xd8\xff",),
    },
    "image/png": {
        "extension": "png",
        "magic": (b"\x89PNG\r\n\x1a\n",),
    },
}


def _require_draft(event: Event) -> None:
    if event.status != Event.DRAFT:
        raise ConflictError(
            code="EVENT_NOT_DRAFT",
            message=("Cette opération n est autorisée " "que sur un événement brouillon."),
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


def _require_event_state(
    event: Event,
    *,
    allowed_states: set[str],
    target_state: str,
) -> None:
    if event.status not in allowed_states:
        raise InvalidStateTransitionError(
            details={
                "current_state": event.status,
                "target_state": target_state,
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

    value = queryset.aggregate(total=Sum("quota"))["total"]

    return int(value or 0)


def _validate_quota_capacity(
    *,
    event: Event,
    quota_total: int,
) -> None:
    if event.capacity_total is None:
        raise ValidationError(
            {"capacity_total": ("Définissez la capacité totale " "avant les catégories de billets.")}
        )

    if quota_total > event.capacity_total:
        raise ValidationError(
            {"quota": ("La somme des quotas dépasse " "la capacité totale de l événement.")}
        )


def _validate_event_image(
    uploaded_file: Any,
) -> str:
    if uploaded_file is None:
        raise ValidationError({"image": ("Le fichier image est requis.")})

    size = int(
        getattr(
            uploaded_file,
            "size",
            0,
        )
        or 0
    )

    if size <= 0:
        raise ValidationError({"image": ("Le fichier image est vide.")})

    if size > EVENT_IMAGE_MAX_BYTES:
        raise ValidationError({"image": ("Le visuel ne doit pas " "dépasser 5 Mo.")})

    declared_type = (
        str(
            getattr(
                uploaded_file,
                "content_type",
                "",
            )
            or ""
        )
        .split(
            ";",
            1,
        )[0]
        .strip()
        .lower()
    )

    expected = EVENT_IMAGE_TYPES.get(declared_type)

    if expected is None:
        raise ValidationError({"image": ("Formats autorisés : " "PNG et JPEG.")})

    header = uploaded_file.read(16)
    uploaded_file.seek(0)

    if not any(header.startswith(prefix) for prefix in expected["magic"]):
        raise ValidationError({"image": ("Le contenu du fichier ne " "correspond pas à son type.")})

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

        if user is not None and getattr(
            user,
            "is_authenticated",
            False,
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

    def get_owned_event(
        self,
        request: Request,
        event_id: Any,
        *,
        for_update: bool = False,
    ) -> Event:
        queryset = Event.objects.select_related("category").filter(
            pk=event_id,
            organizer_id=request.organizer_id,
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
            key = resolve_local_presigned_key(token)
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

        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

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
                message=("Aucun visuel n est associé " "à cet événement."),
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
                message=("Le visuel de cet événement " "est introuvable."),
            ) from exc

        response = Response(
            {
                "url": url,
                "expires_in": (EVENT_IMAGE_URL_TTL_SECONDS),
                "version": event.version,
            },
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(event.version)

        return response

    def put(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        expected_version = parse_if_match(request.headers.get("If-Match"))

        initial_event = self.get_object(
            request,
            event_id,
        )

        _require_draft(initial_event)

        uploaded_file = request.FILES.get("image")

        extension = _validate_event_image(uploaded_file)

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
                    expected_version=(expected_version),
                    updates={
                        "image_key": new_key,
                    },
                )

                event.refresh_from_db()

                if old_key and old_key != new_key:
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

        response["ETag"] = format_etag(new_version)

        return response

    def delete(
        self,
        request: Request,
        event_id: Any,
    ) -> Response:
        expected_version = parse_if_match(request.headers.get("If-Match"))

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
                    message=("Aucun visuel n est associé " "à cet événement."),
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

        response["ETag"] = format_etag(new_version)

        return response


class CategoryListView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        CategoryCollectionPermission,
    ]

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
                context={
                    "organizer_id": (request.organizer_id),
                },
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id="catalog_categories_create",
        summary="Créer une catégorie d événement",
        request=CategoryWriteSerializer,
        responses={
            201: CategorySerializer,
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
        serializer = CategoryWriteSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                category = Category.objects.create(
                    organizer_id=(request.organizer_id),
                    **serializer.validated_data,
                )
        except IntegrityError as exc:
            raise ConflictError(
                code="CATEGORY_ALREADY_EXISTS",
                message=("Une catégorie portant ce nom " "existe déjà."),
            ) from exc

        response = Response(
            CategorySerializer(
                category,
                context={
                    "organizer_id": (request.organizer_id),
                },
            ).data,
            status=status.HTTP_201_CREATED,
        )

        response["ETag"] = format_etag(category.version)

        return response


class CategoryDetailView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        CategoryResourcePermission,
    ]

    def get_object(
        self,
        request: Request,
        category_id: Any,
        *,
        for_update: bool = False,
    ) -> Category:
        queryset = Category.objects.filter(
            pk=category_id,
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
        operation_id="catalog_categories_delete",
        summary="Supprimer ma catégorie d événement",
        responses={
            204: None,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
            409: ERROR_RESPONSE,
        },
    )
    def delete(
        self,
        request: Request,
        category_id: Any,
    ) -> Response:
        with transaction.atomic():
            category = self.get_object(
                request,
                category_id,
                for_update=True,
            )

            if category.events.exists():
                raise ConflictError(
                    code="CATEGORY_IN_USE",
                    message=("Cette catégorie est utilisée " "par au moins un événement."),
                )

            category.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
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
            Event.objects.filter(
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

        data = dict(serializer.validated_data)

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
                message=("Un événement portant ce nom existe " "déjà pour votre organisation."),
            ) from exc

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )

        response["ETag"] = format_etag(event.version)

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

        response["ETag"] = format_etag(event.version)

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
        expected_version = parse_if_match(request.headers.get("If-Match"))

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

                updates = dict(serializer.validated_data)

                category = updates.pop(
                    "category",
                    None,
                )

                if category is not None:
                    updates["category_id"] = category.pk

                if "capacity_total" in updates:
                    quota_total = _ticket_quota_total(event)

                    capacity = updates["capacity_total"]

                    if quota_total > 0 and capacity is None:
                        raise ValidationError(
                            {
                                "capacity_total": (
                                    "La capacité ne peut pas "
                                    "être supprimée tant que "
                                    "des quotas existent."
                                )
                            }
                        )

                    if capacity is not None and quota_total > capacity:
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
                    expected_version=(expected_version),
                    updates=updates,
                )

                event.refresh_from_db()

        except IntegrityError as exc:
            raise ConflictError(
                code="EVENT_ALREADY_EXISTS",
                message=("Un événement portant ce nom existe " "déjà pour votre organisation."),
            ) from exc

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(new_version)

        return response

    @extend_schema(
        operation_id="catalog_events_delete",
        summary="Supprimer un événement brouillon",
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
    ) -> Response:
        expected_version = parse_if_match(request.headers.get("If-Match"))

        with transaction.atomic():
            event = self.get_object(
                request,
                event_id,
                for_update=True,
            )

            _require_draft(event)

            if event.version != expected_version:
                raise StaleResourceError(
                    details={
                        "current_version": (event.version),
                    }
                )

            if event.ticket_categories.filter(sold_count__gt=0).exists():
                raise ConflictError(
                    code="EVENT_HAS_SALES",
                    message=("Ce brouillon possède déjà des " "ventes et ne peut pas être " "supprimé."),
                )

            image_key = event.image_key

            event.delete()

            if image_key:
                transaction.on_commit(
                    lambda key=image_key: (
                        _safe_storage_delete(
                            storage=(build_object_storage()),
                            key=key,
                        )
                    )
                )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


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
        expected_version = parse_if_match(request.headers.get("If-Match"))

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
                errors["venue"] = "Le lieu est requis avant publication."

            if event.capacity_total is None:
                errors["capacity_total"] = "La capacité totale est requise " "avant publication."

            categories = TicketCategory.objects.filter(event=event)

            category_count = categories.count()

            quota_total = int(categories.aggregate(total=Sum("quota"))["total"] or 0)

            if category_count == 0:
                errors["ticket_categories"] = (
                    "Ajoutez au moins une catégorie " "de billets avant publication."
                )

            if event.capacity_total is not None and quota_total > event.capacity_total:
                errors["quota"] = "La somme des quotas dépasse " "la capacité totale."

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

        response["ETag"] = format_etag(new_version)

        return response


class EventPostponeView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventPostponePermission,
    ]

    @extend_schema(
        operation_id="catalog_events_postpone",
        summary="Reporter un événement",
        request=EventPostponeSerializer,
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

        serializer = EventPostponeSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

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

            _require_event_state(
                event,
                allowed_states={
                    Event.PUBLISHED,
                    Event.POSTPONED,
                },
                target_state=Event.POSTPONED,
            )

            previous_starts_at = event.starts_at
            previous_ends_at = event.ends_at
            changed_at = timezone.now()

            new_starts_at = data.get("starts_at")
            new_ends_at = data.get("ends_at")
            has_new_schedule = new_starts_at is not None and new_ends_at is not None

            is_defining_new_date = (
                event.status == Event.POSTPONED
                and event.postponed_to_starts_at is None
                and event.postponed_to_ends_at is None
                and has_new_schedule
            )

            report_reason = data.get(
                "reason",
                "",
            ).strip()

            if not is_defining_new_date and not report_reason:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"reason": ("Le motif du report est requis.")})

            lifecycle_reason = event.lifecycle_reason if is_defining_new_date else report_reason

            # Premier report : la programmation actuelle devient
            # l'ancienne programmation.
            #
            # Si un événement déjà reporté sans nouvelle date reçoit
            # ensuite sa nouvelle programmation, on conserve bien
            # l'ancienne date initiale.
            if (
                event.status != Event.POSTPONED
                or event.postponed_from_starts_at is None
                or event.postponed_to_starts_at is not None
            ):
                postponed_from_starts_at = event.starts_at
                postponed_from_ends_at = event.ends_at
            else:
                postponed_from_starts_at = event.postponed_from_starts_at
                postponed_from_ends_at = event.postponed_from_ends_at

            updates = {
                "status": Event.POSTPONED,
                "postponed_from_starts_at": (postponed_from_starts_at),
                "postponed_from_ends_at": (postponed_from_ends_at),
                "postponed_to_starts_at": new_starts_at,
                "postponed_to_ends_at": new_ends_at,
                "lifecycle_reason": lifecycle_reason,
                "lifecycle_changed_at": changed_at,
            }

            if has_new_schedule:
                updates["starts_at"] = new_starts_at
                updates["ends_at"] = new_ends_at

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates=updates,
            )

            event.refresh_from_db()

            publish_event(
                event_type=CATALOG_EVENT_POSTPONED,
                aggregate_type=AGGREGATE_EVENT,
                aggregate_id=event.pk,
                actor_id=request.user.pk,
                payload=event_lifecycle_payload(
                    status=Event.POSTPONED,
                    reason=lifecycle_reason,
                    notify_buyers=data["notify_buyers"],
                    starts_at=event.starts_at,
                    ends_at=event.ends_at,
                    previous_starts_at=(previous_starts_at),
                    previous_ends_at=(previous_ends_at),
                ),
            )

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(new_version)
        return response


class EventSuspendView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventSuspendPermission,
    ]

    @extend_schema(
        operation_id="catalog_events_suspend",
        summary="Suspendre un événement",
        request=EventSuspendSerializer,
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

        serializer = EventSuspendSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

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

            _require_event_state(
                event,
                allowed_states={
                    Event.PUBLISHED,
                    Event.POSTPONED,
                },
                target_state=Event.SUSPENDED,
            )

            changed_at = timezone.now()

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates={
                    "status": Event.SUSPENDED,
                    "lifecycle_reason": data["reason"],
                    "lifecycle_changed_at": changed_at,
                },
            )

            event.refresh_from_db()

            publish_event(
                event_type=CATALOG_EVENT_SUSPENDED,
                aggregate_type=AGGREGATE_EVENT,
                aggregate_id=event.pk,
                actor_id=request.user.pk,
                payload=event_lifecycle_payload(
                    status=Event.SUSPENDED,
                    reason=data["reason"],
                    notify_buyers=data["notify_buyers"],
                ),
            )

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(new_version)
        return response


class EventCancelView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventCancelPermission,
    ]

    @extend_schema(
        operation_id="catalog_events_cancel",
        summary="Annuler un événement",
        request=EventCancelSerializer,
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

        serializer = EventCancelSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

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

            _require_event_state(
                event,
                allowed_states={
                    Event.PUBLISHED,
                    Event.POSTPONED,
                    Event.SUSPENDED,
                },
                target_state=Event.CANCELLED,
            )

            changed_at = timezone.now()

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates={
                    "status": Event.CANCELLED,
                    "lifecycle_reason": data["reason"],
                    "lifecycle_changed_at": changed_at,
                },
            )

            event.refresh_from_db()

            publish_event(
                event_type=CATALOG_EVENT_CANCELLED,
                aggregate_type=AGGREGATE_EVENT,
                aggregate_id=event.pk,
                actor_id=request.user.pk,
                payload=event_lifecycle_payload(
                    status=Event.CANCELLED,
                    reason=data["reason"],
                    notify_buyers=data["notify_buyers"],
                    refund_requested=(data["refund_requested"]),
                ),
            )

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )
        response["ETag"] = format_etag(new_version)
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

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

            _require_published_for_archive(event)

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

        response["ETag"] = format_etag(new_version)

        return response


class EventUnarchiveView(
    CatalogOrganizerContextMixin,
    APIView,
):
    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventUnarchivePermission,
    ]

    @extend_schema(
        operation_id="catalog_events_unarchive",
        summary="Désarchiver un événement",
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

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

            _require_event_state(
                event,
                allowed_states={
                    Event.ARCHIVED,
                },
                target_state=Event.PUBLISHED,
            )

            new_version = versioned_update(
                model=Event,
                pk=event.pk,
                expected_version=expected_version,
                updates={
                    "status": Event.PUBLISHED,
                },
            )

            event.refresh_from_db()

        response = Response(
            EventSerializer(event).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(new_version)

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
        operation_id=("catalog_ticket_categories_list"),
        summary=("Lister les catégories de billets " "d un événement"),
        responses={
            200: TicketCategorySerializer(many=True),
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

        queryset = TicketCategory.objects.filter(event=event).order_by(
            "created_at",
            "id",
        )

        return Response(
            TicketCategorySerializer(
                queryset,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id=("catalog_ticket_categories_create"),
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
        serializer = TicketCategoryWriteSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = dict(serializer.validated_data)

        try:
            with transaction.atomic():
                event = self.get_owned_event(
                    request,
                    event_id,
                    for_update=True,
                )

                _require_draft(event)

                quota_total = _ticket_quota_total(event) + data["quota"]

                _validate_quota_capacity(
                    event=event,
                    quota_total=quota_total,
                )

                category = TicketCategory.objects.create(
                    event=event,
                    **data,
                )

        except IntegrityError as exc:
            raise ConflictError(
                code=("TICKET_CATEGORY_ALREADY_EXISTS"),
                message=("Une catégorie portant ce nom " "existe déjà pour cet événement."),
            ) from exc

        response = Response(
            TicketCategorySerializer(category).data,
            status=status.HTTP_201_CREATED,
        )

        response["ETag"] = format_etag(category.version)

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
        queryset = TicketCategory.objects.select_related("event").filter(
            pk=ticket_category_id,
            event=event,
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
        operation_id=("catalog_ticket_categories_retrieve"),
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
            ticket_category_id=(ticket_category_id),
        )

        response = Response(
            TicketCategorySerializer(category).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(category.version)

        return response

    @extend_schema(
        operation_id=("catalog_ticket_categories_update"),
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

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
                    ticket_category_id=(ticket_category_id),
                    for_update=True,
                )

                serializer = TicketCategoryWriteSerializer(
                    data=request.data,
                    partial=True,
                    context={
                        "ticket_category": category,
                    },
                )

                serializer.is_valid(
                    raise_exception=True,
                )

                updates = dict(serializer.validated_data)

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
                    expected_version=(expected_version),
                    updates=updates,
                )

                category.refresh_from_db()

        except IntegrityError as exc:
            raise ConflictError(
                code=("TICKET_CATEGORY_ALREADY_EXISTS"),
                message=("Une catégorie portant ce nom " "existe déjà pour cet événement."),
            ) from exc

        response = Response(
            TicketCategorySerializer(category).data,
            status=status.HTTP_200_OK,
        )

        response["ETag"] = format_etag(new_version)

        return response

    @extend_schema(
        operation_id=("catalog_ticket_categories_delete"),
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
        expected_version = parse_if_match(request.headers.get("If-Match"))

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
                ticket_category_id=(ticket_category_id),
                for_update=True,
            )

            if category.sold_count > 0:
                raise ConflictError(
                    code=("TICKET_CATEGORY_HAS_SALES"),
                    message=("Une catégorie ayant déjà " "des ventes ne peut pas être " "supprimée."),
                )

            versioned_update(
                model=TicketCategory,
                pk=category.pk,
                expected_version=(expected_version),
                updates={},
            )

            category.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


def _require_event_scanner_assignment_allowed(
    event: Event,
) -> None:
    """
    Une nouvelle affectation commence uniquement après publication.

    POSTPONED reste un événement déjà publié et peut être préparé.
    """

    if event.status not in {
        Event.PUBLISHED,
        Event.POSTPONED,
    }:
        raise ConflictError(
            code=("EVENT_SCANNER_ASSIGNMENT_" "NOT_ALLOWED"),
            message=(
                "L'affectation des scanners est " "autorisée uniquement après " "publication de l'événement."
            ),
            details={
                "event_status": event.status,
            },
        )


def _event_scanner_assignment_payload(
    assignment: EventScannerAssignment,
    scanner_summary: Any,
) -> dict[str, Any]:
    return {
        "assignment_id": assignment.pk,
        "scanner_id": scanner_summary.id,
        "first_name": (scanner_summary.first_name),
        "last_name": (scanner_summary.last_name),
        "email": scanner_summary.email,
        "status": scanner_summary.status,
        "scanner_version": (scanner_summary.version),
        "assigned_at": assignment.created_at,
    }


class AdminOrganizerEventListView(APIView):
    """
    Lecture administrative des événements d'un organisateur.

    Cette surface est strictement en lecture seule.
    Chaque événement expose également ses catégories de billets
    afin d'afficher prix, quota et nombre vendu dans la console admin.
    """

    permission_classes = [
        IsAuthenticated,
        ActionPermission,
    ]
    required_action = Action.ORGANIZER_READ

    @extend_schema(
        operation_id="catalog_admin_organizer_events_list",
        summary=("Lister les événements et ventes " "d'un organisateur"),
        responses={
            200: EventSerializer(many=True),
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
        organizer_id: Any,
    ) -> Response:
        # Comme les autres surfaces admin organizer :
        # Resource() impose la portée administrative ANY.
        self.check_object_permissions(
            request,
            Resource(),
        )

        queryset = (
            Event.objects.filter(
                organizer_id=organizer_id,
            )
            .select_related("category")
            .prefetch_related(
                "ticket_categories",
            )
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

        events = page if page is not None else list(queryset)

        payload = []

        for event in events:
            event_data = dict(
                EventSerializer(
                    event,
                ).data
            )

            event_data["ticket_categories"] = TicketCategorySerializer(
                event.ticket_categories.all(),
                many=True,
            ).data

            payload.append(event_data)

        if page is not None:
            return paginator.get_paginated_response(payload)

        return Response(
            payload,
            status=status.HTTP_200_OK,
        )


class EventScannerAssignmentCollectionView(
    CatalogOrganizerContextMixin,
    APIView,
):
    """
    GET  /api/v1/events/{event_id}/scanners
    POST /api/v1/events/{event_id}/scanners
    """

    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventScannerAssignmentPermission,
    ]

    @extend_schema(
        operation_id=("catalog_events_scanners_list"),
        summary=("Lister les scanners affectés " "à un événement"),
        responses={
            200: EventScannerAssignmentSerializer(
                many=True,
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

        self.check_object_permissions(
            request,
            event,
        )

        assignments = list(
            EventScannerAssignment.objects.filter(
                event=event,
                unassigned_at__isnull=True,
            ).order_by(
                "created_at",
                "pk",
            )
        )

        summaries = {
            summary.id: summary
            for summary in list_scanner_assignment_summaries(
                organizer_id=(request.organizer_id),
                scanner_ids=[assignment.scanner_id for assignment in assignments],
            )
        }

        payload = []

        for assignment in assignments:
            summary = summaries.get(assignment.scanner_id)

            if summary is None:
                continue

            payload.append(
                _event_scanner_assignment_payload(
                    assignment,
                    summary,
                )
            )

        return Response(
            EventScannerAssignmentSerializer(
                payload,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        operation_id=("catalog_events_scanners_assign"),
        summary=("Affecter manuellement un scanner " "à un événement"),
        request=EventScannerAssignSerializer,
        responses={
            200: EventScannerAssignmentSerializer,
            201: EventScannerAssignmentSerializer,
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
        serializer = EventScannerAssignSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        scanner_id = serializer.validated_data["scanner_id"]

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

            _require_event_scanner_assignment_allowed(
                event,
            )

            scanner_summary = get_scanner_assignment_summary(
                organizer_id=(request.organizer_id),
                scanner_id=scanner_id,
                assignable_only=True,
            )

            if scanner_summary is None:
                raise NotFoundBusinessError(
                    code="SCANNER_NOT_ASSIGNABLE",
                    message=("Scanner introuvable ou " "non affectable pour cet " "organisateur."),
                )

            assignment, created = EventScannerAssignment.objects.get_or_create(
                event=event,
                scanner_id=(scanner_summary.id),
                unassigned_at=None,
                defaults={
                    "assigned_by_id": (request.user.pk),
                },
            )

            if created:
                publish_event(
                    event_type=(CATALOG_EVENT_SCANNER_ASSIGNED),
                    aggregate_type=(AGGREGATE_EVENT),
                    aggregate_id=event.pk,
                    actor_id=request.user.pk,
                    payload={
                        "assignment_id": str(assignment.pk),
                        "scanner_id": str(scanner_summary.id),
                    },
                )

        return Response(
            EventScannerAssignmentSerializer(
                _event_scanner_assignment_payload(
                    assignment,
                    scanner_summary,
                )
            ).data,
            status=(status.HTTP_201_CREATED if created else status.HTTP_200_OK),
        )


class EventScannerAssignmentDetailView(
    CatalogOrganizerContextMixin,
    APIView,
):
    """
    DELETE
    /api/v1/events/{event_id}/scanners/{scanner_id}
    """

    permission_classes = [
        IsAuthenticated,
        IsApprovedOrganizer,
        EventScannerAssignmentPermission,
    ]

    @extend_schema(
        operation_id=("catalog_events_scanners_unassign"),
        summary=("Désaffecter manuellement un scanner " "d'un événement"),
        responses={
            204: None,
            401: ERROR_RESPONSE,
            403: ERROR_RESPONSE,
            404: ERROR_RESPONSE,
        },
    )
    def delete(
        self,
        request: Request,
        event_id: Any,
        scanner_id: Any,
    ) -> Response:
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

            assignment = (
                EventScannerAssignment.objects.select_for_update()
                .filter(
                    event=event,
                    scanner_id=scanner_id,
                    unassigned_at__isnull=True,
                )
                .first()
            )

            if assignment is None:
                raise NotFoundBusinessError(
                    code=("EVENT_SCANNER_ASSIGNMENT_" "NOT_FOUND"),
                    message=("Cette affectation " "n'existe pas."),
                )

            assignment.unassigned_at = timezone.now()
            assignment.unassigned_by_id = request.user.pk

            assignment.save(
                update_fields=[
                    "unassigned_at",
                    "unassigned_by_id",
                    "updated_at",
                ]
            )

            publish_event(
                event_type=(CATALOG_EVENT_SCANNER_UNASSIGNED),
                aggregate_type=(AGGREGATE_EVENT),
                aggregate_id=event.pk,
                actor_id=request.user.pk,
                payload={
                    "assignment_id": str(assignment.pk),
                    "scanner_id": str(scanner_id),
                },
            )

        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )
