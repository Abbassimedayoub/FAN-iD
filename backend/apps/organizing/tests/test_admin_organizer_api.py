from __future__ import annotations

import datetime
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.core.outbox.models import OutboxEvent
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_PENDING,
    ORGANIZER_REJECTED,
    ORGANIZER_SUSPENDED,
)
from apps.organizing.models import Organizer
from apps.organizing.views import OrganizerApproveView, OrganizerRejectView, OrganizerSuspendView

User = get_user_model()

PASSWORD = "Chataigne-Orageuse-2026"

AUTH_LEVEL_PASSWORD = 1
AUTH_LEVEL_STEP_UP = 2


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


@pytest.fixture
def admin(db, roles):
    return User.objects.create_user(
        email="organizer-admin@example.test",
        password=PASSWORD,
        first_name="Admin",
        last_name="FanID",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ADMIN"],
    )


@pytest.fixture
def fan(db, roles):
    return User.objects.create_user(
        email="organizer-fan@example.test",
        password=PASSWORD,
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1996, 5, 4),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )


@pytest.fixture
def organizer_user(db, roles):
    return User.objects.create_user(
        email="organizer-owner@example.test",
        password=PASSWORD,
        first_name="Nora",
        last_name="Amari",
        date_of_birth=datetime.date(1992, 4, 7),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )


@pytest.fixture
def organizer(organizer_user):
    return Organizer.objects.create(
        user=organizer_user,
        org_name="Arena Paris",
        contact_email="contact@arena.example.test",
    )


def call(
    factory: APIRequestFactory,
    *,
    view,
    user,
    organizer_id,
    auth_level: int = AUTH_LEVEL_STEP_UP,
    if_match: str | None = '"1"',
    data: dict | None = None,
):
    headers = {}
    if if_match is not None:
        headers["HTTP_IF_MATCH"] = if_match

    request = factory.post(
        "/api/v1/admin/organizers/action",
        data or {},
        format="json",
        **headers,
    )
    force_authenticate(request, user=user)
    setattr(request, "auth_level", auth_level)  # noqa: B010

    return view.as_view()(request, organizer_id=organizer_id)


def test_admin_can_approve_pending_organizer(factory, admin, organizer):
    response = call(
        factory,
        view=OrganizerApproveView,
        user=admin,
        organizer_id=organizer.pk,
    )

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"2"'

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.version == 2
    assert organizer.validated_by_id == admin.pk
    assert organizer.validated_at is not None
    assert organizer.rejection_reason is None

    event = OutboxEvent.objects.get()
    assert event.event_type == "organizing.organizer.approved"
    assert event.aggregate_id == organizer.pk
    assert event.actor_id == admin.pk


def test_admin_can_reject_pending_organizer(factory, admin, organizer):
    response = call(
        factory,
        view=OrganizerRejectView,
        user=admin,
        organizer_id=organizer.pk,
        data={"reason": "Dossier incomplet"},
    )

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"2"'

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_REJECTED
    assert organizer.version == 2
    assert organizer.validated_by_id == admin.pk
    assert organizer.rejection_reason == "Dossier incomplet"

    event = OutboxEvent.objects.get()
    assert event.event_type == "organizing.organizer.rejected"
    assert event.aggregate_id == organizer.pk
    assert event.actor_id == admin.pk


def test_admin_can_suspend_approved_organizer_without_outbox(
    factory,
    admin,
    organizer,
):
    Organizer.objects.filter(pk=organizer.pk).update(validation_status=ORGANIZER_APPROVED)

    response = call(
        factory,
        view=OrganizerSuspendView,
        user=admin,
        organizer_id=organizer.pk,
    )

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"2"'

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_SUSPENDED
    assert organizer.version == 2
    assert OutboxEvent.objects.count() == 0


@pytest.mark.parametrize(
    "view,data",
    [
        (OrganizerApproveView, {}),
        (OrganizerRejectView, {"reason": "Refus"}),
        (OrganizerSuspendView, {}),
    ],
)
def test_admin_actions_require_if_match(
    factory,
    admin,
    organizer,
    view,
    data,
):
    if view is OrganizerSuspendView:
        Organizer.objects.filter(pk=organizer.pk).update(validation_status=ORGANIZER_APPROVED)

    response = call(
        factory,
        view=view,
        user=admin,
        organizer_id=organizer.pk,
        if_match=None,
        data=data,
    )

    assert response.status_code == 428, response.data
    assert response.data["error"]["code"] == "PRECONDITION_REQUIRED"

    organizer.refresh_from_db()
    assert organizer.version == 1


def test_stale_version_returns_current_version(factory, admin, organizer):
    Organizer.objects.filter(pk=organizer.pk).update(version=2)

    response = call(
        factory,
        view=OrganizerApproveView,
        user=admin,
        organizer_id=organizer.pk,
        if_match='"1"',
    )

    assert response.status_code == 409, response.data
    assert response.data["error"]["code"] == "STALE_RESOURCE"
    assert response.data["error"]["details"]["current_version"] == 2

    organizer.refresh_from_db()
    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.version == 2
    assert OutboxEvent.objects.count() == 0


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reject_requires_a_non_blank_reason(
    factory,
    admin,
    organizer,
    reason,
):
    data = {} if reason is None else {"reason": reason}

    response = call(
        factory,
        view=OrganizerRejectView,
        user=admin,
        organizer_id=organizer.pk,
        data=data,
    )

    assert response.status_code == 400, response.data

    organizer.refresh_from_db()
    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.version == 1
    assert OutboxEvent.objects.count() == 0


def test_invalid_transition_is_rejected(factory, admin, organizer):
    Organizer.objects.filter(pk=organizer.pk).update(validation_status=ORGANIZER_REJECTED)

    response = call(
        factory,
        view=OrganizerApproveView,
        user=admin,
        organizer_id=organizer.pk,
    )

    assert response.status_code == 409, response.data
    assert response.data["error"]["code"] == "INVALID_STATE_TRANSITION"

    organizer.refresh_from_db()
    assert organizer.validation_status == ORGANIZER_REJECTED
    assert organizer.version == 1
    assert OutboxEvent.objects.count() == 0


def test_admin_password_only_requires_step_up(factory, admin, organizer):
    response = call(
        factory,
        view=OrganizerApproveView,
        user=admin,
        organizer_id=organizer.pk,
        auth_level=AUTH_LEVEL_PASSWORD,
    )

    assert response.status_code == 403, response.data


def test_fan_cannot_perform_admin_action(factory, fan, organizer):
    response = call(
        factory,
        view=OrganizerApproveView,
        user=fan,
        organizer_id=organizer.pk,
    )

    assert response.status_code == 403, response.data


def test_organizer_cannot_perform_admin_action(
    factory,
    organizer_user,
    organizer,
):
    response = call(
        factory,
        view=OrganizerApproveView,
        user=organizer_user,
        organizer_id=organizer.pk,
    )

    assert response.status_code == 403, response.data


def test_unknown_organizer_returns_404(factory, admin):
    response = call(
        factory,
        view=OrganizerApproveView,
        user=admin,
        organizer_id=uuid.uuid4(),
    )

    assert response.status_code == 404, response.data


def list_call(factory: APIRequestFactory, *, user, query: str = ""):
    request = factory.get(f"/api/v1/admin/organizers/{query}")
    force_authenticate(request, user=user)
    setattr(request, "auth_level", AUTH_LEVEL_STEP_UP)  # noqa: B010
    from apps.organizing.views import AdminOrganizerListView

    return AdminOrganizerListView.as_view()(request)


def test_admin_can_list_organizers(factory, admin, organizer):
    response = list_call(factory, user=admin)

    assert response.status_code == 200, response.data
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(organizer.pk)


def test_organizer_cannot_list_all_organizers(factory, organizer_user, organizer):
    response = list_call(factory, user=organizer_user)

    assert response.status_code == 403, response.data


def test_fan_cannot_list_all_organizers(factory, fan, organizer):
    response = list_call(factory, user=fan)

    assert response.status_code == 403, response.data


def test_scanner_cannot_list_all_organizers(factory, roles, organizer):
    scanner = User.objects.create_user(
        email="scanner-list@example.test",
        password=PASSWORD,
        first_name="Scan",
        last_name="Ner",
        date_of_birth=datetime.date(1994, 5, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
    )

    response = list_call(factory, user=scanner)

    assert response.status_code == 403, response.data


def test_admin_list_filters_by_validation_status(factory, admin, organizer, roles):
    approved_user = User.objects.create_user(
        email="approved-list@example.test",
        password=PASSWORD,
        first_name="Approved",
        last_name="Org",
        date_of_birth=datetime.date(1991, 6, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )
    approved = Organizer.objects.create(
        user=approved_user,
        org_name="Approved Venue",
        contact_email="approved@example.test",
        validation_status=ORGANIZER_APPROVED,
    )

    response = list_call(
        factory,
        user=admin,
        query="?validation_status=APPROVED",
    )

    assert response.status_code == 200, response.data
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(approved.pk)


def test_admin_list_is_paginated(factory, admin, roles):
    for index in range(25):
        user = User.objects.create_user(
            email=f"list-{index}@example.test",
            password=PASSWORD,
            first_name="List",
            last_name=str(index),
            date_of_birth=datetime.date(1990, 1, 1),
            terms_accepted_at=timezone.now(),
            role=roles["ORGANIZER"],
        )
        Organizer.objects.create(
            user=user,
            org_name=f"Venue {index:02d}",
            contact_email=f"venue-{index}@example.test",
        )

    response = list_call(factory, user=admin)

    assert response.status_code == 200, response.data
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 20


def test_admin_list_page_size_is_capped_at_100(factory, admin, roles):
    for index in range(105):
        user = User.objects.create_user(
            email=f"cap-{index}@example.test",
            password=PASSWORD,
            first_name="Cap",
            last_name=str(index),
            date_of_birth=datetime.date(1990, 1, 1),
            terms_accepted_at=timezone.now(),
            role=roles["ORGANIZER"],
        )
        Organizer.objects.create(
            user=user,
            org_name=f"Cap Venue {index:03d}",
            contact_email=f"cap-{index}@example.test",
        )

    response = list_call(factory, user=admin, query="?page_size=999")

    assert response.status_code == 200, response.data
    assert response.data["count"] == 105
    assert len(response.data["results"]) == 100
