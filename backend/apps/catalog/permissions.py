from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS

from apps.identity.api import (
    Action,
    ActionPermission,
    OrganizerResourcePermission,
)


class EventCollectionPermission(ActionPermission):
    """
    POST /events crée ; GET /events lit la collection propriétaire.

    La portée d instance de EVENT_READ est appliquée par le filtrage du
    queryset. Aucun événement d un autre organisateur n entre dans la
    collection.
    """

    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.EVENT_READ

        if request.method == "POST":
            return Action.EVENT_CREATE

        return None


class EventResourcePermission(OrganizerResourcePermission):
    """Permission ABAC pour un événement individuel."""

    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.EVENT_READ

        if request.method in {"PATCH", "PUT"}:
            return Action.EVENT_UPDATE

        return None
