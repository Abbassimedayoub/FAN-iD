from __future__ import annotations

import uuid

from django.urls import resolve

from apps.catalog.views import (
    AdminOrganizerEventListView,
)
from apps.identity.api import Action


def test_admin_organizer_event_route_is_mounted():
    organizer_id = uuid.uuid4()

    match = resolve(("/api/v1/admin/organizers/" f"{organizer_id}/events"))

    assert match.func.view_class is AdminOrganizerEventListView

    assert match.kwargs["organizer_id"] == organizer_id


def test_admin_organizer_event_surface_uses_organizer_read():
    assert AdminOrganizerEventListView.required_action is Action.ORGANIZER_READ


def test_admin_organizer_event_surface_is_read_only():
    assert "post" not in AdminOrganizerEventListView.__dict__
    assert "patch" not in AdminOrganizerEventListView.__dict__
    assert "put" not in AdminOrganizerEventListView.__dict__
    assert "delete" not in AdminOrganizerEventListView.__dict__
