from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.catalog.models import (
    Event,
    EventScannerAssignment,
)

from .test_event_scanner_assignment_api import (
    client_for,
    make_event,
    make_organizer,
    make_scanner,
)

PORTAL_URL = "/api/v1/scanner/events"


@pytest.mark.django_db
def test_scanner_sees_only_its_active_assignments(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="portal-owner",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="portal-main",
        status="ACTIVE",
    )

    other_scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="portal-other",
        status="ACTIVE",
    )

    assigned_event = make_event(
        organizer=organizer,
        suffix="portal-assigned",
        status=Event.POSTPONED,
    )

    assigned_event.postponed_from_starts_at = assigned_event.starts_at - datetime.timedelta(days=1)
    assigned_event.postponed_from_ends_at = assigned_event.ends_at - datetime.timedelta(days=1)
    assigned_event.postponed_to_starts_at = assigned_event.starts_at
    assigned_event.postponed_to_ends_at = assigned_event.ends_at
    assigned_event.lifecycle_reason = "Stade indisponible"
    assigned_event.lifecycle_changed_at = timezone.now()
    assigned_event.save(
        update_fields=[
            "postponed_from_starts_at",
            "postponed_from_ends_at",
            "postponed_to_starts_at",
            "postponed_to_ends_at",
            "lifecycle_reason",
            "lifecycle_changed_at",
            "updated_at",
        ]
    )

    other_event = make_event(
        organizer=organizer,
        suffix="portal-other-event",
    )

    removed_event = make_event(
        organizer=organizer,
        suffix="portal-removed",
    )

    EventScannerAssignment.objects.create(
        event=assigned_event,
        scanner_id=scanner.pk,
        assigned_by_id=owner.pk,
    )

    EventScannerAssignment.objects.create(
        event=other_event,
        scanner_id=other_scanner.pk,
        assigned_by_id=owner.pk,
    )

    EventScannerAssignment.objects.create(
        event=removed_event,
        scanner_id=scanner.pk,
        assigned_by_id=owner.pk,
        unassigned_at=timezone.now(),
        unassigned_by_id=owner.pk,
    )

    response = client_for(scanner.user).get(PORTAL_URL)

    assert response.status_code == 200
    assert len(response.data) == 1

    item = response.data[0]

    assert item["id"] == str(assigned_event.pk)
    assert item["status"] == Event.POSTPONED
    assert item["lifecycle_reason"] == ("Stade indisponible")
    assert item["venue"] == "Stade FANID"
    assert item["postponed_from_starts_at"] is not None
    assert item["postponed_from_ends_at"] is not None
    assert item["postponed_to_starts_at"] is not None
    assert item["postponed_to_ends_at"] is not None


@pytest.mark.django_db
def test_scanner_cannot_read_event_from_other_scanner_or_organizer(
    roles,
):
    owner_a, organizer_a = make_organizer(
        roles,
        suffix="portal-a",
    )

    owner_b, organizer_b = make_organizer(
        roles,
        suffix="portal-b",
    )

    scanner_a = make_scanner(
        roles,
        organizer=organizer_a,
        owner=owner_a,
        suffix="portal-a",
        status="ACTIVE",
    )

    event_b = make_event(
        organizer=organizer_b,
        suffix="portal-b",
    )

    EventScannerAssignment.objects.create(
        event=event_b,
        scanner_id=scanner_a.pk,
        assigned_by_id=owner_b.pk,
    )

    response = client_for(scanner_a.user).get(PORTAL_URL)

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_organizer_cannot_use_scanner_portal(
    roles,
):
    owner, _ = make_organizer(
        roles,
        suffix="portal-organizer-denied",
    )

    response = client_for(owner).get(PORTAL_URL)

    assert response.status_code == 403


@pytest.mark.django_db
def test_temporary_password_must_be_replaced_before_portal(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="portal-temp",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="portal-temp",
        status="OPENED",
    )

    scanner.user.must_change_password = True
    scanner.user.save(
        update_fields=[
            "must_change_password",
            "updated_at",
        ]
    )

    response = client_for(scanner.user).get(PORTAL_URL)

    assert response.status_code == 403


@pytest.mark.django_db
def test_opened_scanner_can_use_portal_after_password_change(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="portal-opened",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="portal-opened",
        status="OPENED",
    )

    event = make_event(
        organizer=organizer,
        suffix="portal-opened",
    )

    EventScannerAssignment.objects.create(
        event=event,
        scanner_id=scanner.pk,
        assigned_by_id=owner.pk,
    )

    response = client_for(scanner.user).get(PORTAL_URL)

    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [str(event.pk)]
