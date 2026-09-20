"""
Authorization adapters for the `organizing` context.

This module crosses the identity boundary only through its public API. It
identifies resources but never makes authorization decisions; the identity
policy engine remains the source of the verdict.
"""

from __future__ import annotations

from typing import Any, ClassVar

from apps.identity.api import OrganizerResourcePermission, Resource


class OrganizerRecordPermission(OrganizerResourcePermission):
    """OWN_ORGANIZER scope for an organizer dossier whose resource identity is its own primary key."""

    organizer_lookup: ClassVar[str] = "pk"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(
            organizer_id=getattr(obj, self.organizer_lookup, None),
            state=getattr(obj, "validation_status", None),
        )
