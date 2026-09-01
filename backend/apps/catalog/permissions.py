from __future__ import annotations

from typing import Any

from rest_framework.permissions import SAFE_METHODS

from apps.identity.api import (
    Action,
    ActionPermission,
    OrganizerResourcePermission,
)


class CategoryCollectionPermission(ActionPermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.CATEGORY_READ

        if request.method == "POST":
            return Action.CATEGORY_CREATE

        return None


class CategoryResourcePermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "DELETE":
            return Action.CATEGORY_DELETE

        return None


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


class EventResourcePermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.EVENT_READ

        if request.method in {"PATCH", "PUT"}:
            return Action.EVENT_UPDATE

        if request.method == "DELETE":
            return Action.EVENT_DELETE

        return None


class EventPublishPermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_PUBLISH

        return None


class EventArchivePermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_ARCHIVE

        return None


class EventUnarchivePermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_UNARCHIVE

        return None


class EventPostponePermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_POSTPONE

        return None


class EventSuspendPermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_SUSPEND

        return None


class EventCancelPermission(OrganizerResourcePermission):
    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method == "POST":
            return Action.EVENT_CANCEL

        return None


class TicketCategoryCollectionPermission(ActionPermission):
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


class TicketCategoryResourcePermission(OrganizerResourcePermission):
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


class EventImagePermission(OrganizerResourcePermission):
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


class EventScannerAssignmentPermission(
    OrganizerResourcePermission,
):
    """
    GET utilise EVENT_READ.
    POST / DELETE utilisent EVENT_UPDATE.
    """

    def get_action(
        self,
        request: Any,
        view: Any,
    ) -> Action | None:
        if request.method in SAFE_METHODS:
            return Action.EVENT_READ

        if request.method in {
            "POST",
            "DELETE",
        }:
            return Action.EVENT_UPDATE

        return None
