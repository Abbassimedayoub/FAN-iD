from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.openapi import ERROR_RESPONSE
from apps.core.pagination import StandardPagination

from .fan_catalog_serializers import (
    FanCatalogCategorySerializer,
    FanCatalogEventQuerySerializer,
    FanCatalogEventSerializer,
)
from .models import Category, Event


class FanCatalogCategoryListView(APIView):
    """
    Liste des catégories disponibles dans le Catalogue Fan.

    Aucun filtrage basé sur l'Organizer ou sur le statut d'un Event
    n'est appliqué dans ce premier lot.
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        operation_id="fan_catalog_categories_list",
        summary="Lister les catégories du Catalogue Fan",
        responses={
            200: FanCatalogCategorySerializer(many=True),
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        categories = Category.objects.order_by(
            "name",
            "id",
        )

        return Response(
            FanCatalogCategorySerializer(
                categories,
                many=True,
            ).data,
            status=status.HTTP_200_OK,
        )


class FanCatalogEventListView(APIView):
    """
    Liste des événements d'une catégorie pour le Fan.

    Tous les états existants sont conservés :
    DRAFT, PUBLISHED, POSTPONED, SUSPENDED, CANCELLED et ARCHIVED.

    Le Mobile décidera ensuite de leur représentation visuelle.
    """

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        operation_id="fan_catalog_events_list",
        summary="Lister les événements d'une catégorie",
        parameters=[FanCatalogEventQuerySerializer],
        responses={
            200: FanCatalogEventSerializer(many=True),
            400: ERROR_RESPONSE,
        },
    )
    def get(
        self,
        request: Request,
    ) -> Response:
        query_serializer = FanCatalogEventQuerySerializer(
            data=request.query_params,
        )
        query_serializer.is_valid(raise_exception=True)

        category_id = query_serializer.validated_data[
            "category_id"
        ]

        queryset = (
            Event.objects.filter(
                category_id=category_id,
            )
            .select_related("category")
            .order_by(
                "starts_at",
                "id",
            )
        )

        paginator = StandardPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        return paginator.get_paginated_response(
            FanCatalogEventSerializer(
                page,
                many=True,
            ).data
        )
