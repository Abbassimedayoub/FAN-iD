"""Pagination par curseur : stabilité de l'ordre même à timestamps égaux (§55)."""

from apps.core.pagination import CursorPagination, StandardPagination


def test_standard_pagination_default_page_size():
    assert StandardPagination.page_size == 20
    assert StandardPagination.max_page_size == 100


def test_cursor_pagination_orders_on_created_at_then_id_for_stability():
    # Le tie-break sur `id` (second champ d'`ordering`) est ce qui garantit
    # qu'aucune ligne n'est sautée ni dupliquée entre deux pages quand
    # plusieurs lignes partagent exactement le même `created_at` — cas
    # fréquent sur `scan_log` en cas d'écritures en rafale (Sprint 4).
    assert CursorPagination.ordering == ("-created_at", "-id")


def test_cursor_pagination_page_size():
    assert CursorPagination.page_size == 50
