"""Standard page-number and cursor pagination helpers."""

from rest_framework.pagination import CursorPagination as DRFCursorPagination
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Default pagination for reasonably sized lists."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CursorPagination(DRFCursorPagination):
    """
    Cursor pagination for large append-only logs such as scan history.

    `ordering` always includes a unique tie-breaker so pagination remains
    stable when several rows share the same timestamp.
    """

    page_size = 50
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"
