"""Cursor pagination must remain stable even when timestamps are equal."""

from apps.core.pagination import CursorPagination, StandardPagination


def test_standard_pagination_default_page_size():
    assert StandardPagination.page_size == 20
    assert StandardPagination.max_page_size == 100


def test_cursor_pagination_orders_on_created_at_then_id_for_stability():
    # The `id` tie-breaker, as the second ordering field, prevents rows from
    # being skipped or duplicated across pages when multiple rows share the same
    # `created_at` timestamp.
    assert CursorPagination.ordering == ("-created_at", "-id")


def test_cursor_pagination_page_size():
    assert CursorPagination.page_size == 50
