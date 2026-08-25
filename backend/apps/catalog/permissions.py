from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS

from apps.identity.api import (
    Action,
    ActionPermission,
    OrganizerResourcePermission,
)


class EventCollectionPermission(ActionPermission):
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


class EventResourcePermission(
    OrganizerResourcePermission
):
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


class EventPublishPermission(
    OrganizerResourcePermission
):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_PUBLISH

        return None


class EventArchivePermission(
    OrganizerResourcePermission
):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_ARCHIVE

        return None


class TicketCategoryCollectionPermission(
    ActionPermission
):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.TICKET_CATEGORY_READ

        if request.method == "POST":
            return Action.TICKET_CATEGORY_CREATE

        return None


class TicketCategoryResourcePermission(
    OrganizerResourcePermission
):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.TICKET_CATEGORY_READ

        if request.method in {"PATCH", "PUT"}:
            return Action.TICKET_CATEGORY_UPDATE

        if request.method == "DELETE":
            return Action.TICKET_CATEGORY_DELETE

        return None


class EventImagePermission(
    OrganizerResourcePermission
):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.EVENT_READ

        if request.method in {
            "PUT",
            "DELETE",
        }:
            return Action.EVENT_UPDATE

        return None
