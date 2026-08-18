"""Pagination standard (par page) et par curseur (§18 master prompt / §2.2 Source B)."""

from rest_framework.pagination import CursorPagination as DRFCursorPagination
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Pagination par défaut — listes de taille raisonnable (catalogue, mes billets)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CursorPagination(DRFCursorPagination):
    """
    Pagination par curseur — journaux volumineux (ex. `scan_log` au Sprint 4).

    `ordering` doit toujours inclure un champ strictement monotone et unique
    (ex. `-created_at,-id`) pour garantir un ordre stable même si plusieurs
    lignes partagent le même timestamp — sans le tie-break sur `id`, deux
    pages consécutives peuvent se chevaucher ou sauter une ligne.
    """

    page_size = 50
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"
