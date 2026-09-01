from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event, EventScannerAssignment
from apps.core.outbox.models import OutboxEvent

User = get_user_model()

ORGANIZER_APPROVED = "APPROVED"


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=(f"event-scanner-owner-{suffix}" "@example.test"),
        password="Organisateur-Solide-2026!",
        first_name="Nadia",
        last_name="Benali",
        date_of_birth=datetime.date(
            1990,
            5,
            2,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    Organizer = apps.get_model(
        "organizing",
        "Organizer",
    )

    organizer = Organizer.objects.create(
        user=user,
        org_name=(f"Event Scanner Org {suffix}"),
        contact_email=(f"event-scanner-contact-{suffix}" "@example.test"),
        validation_status=(ORGANIZER_APPROVED),
    )

    return user, organizer


def make_scanner(
    roles,
    *,
    organizer,
    owner,
    suffix: str,
    status: str = "ACTIVE",
):
    scanner_user = User.objects.create_user(
        email=(f"event-scanner-{suffix}" "@example.test"),
        password="Scanner-Solide-2026!",
        first_name="Amine",
        last_name=f"Scanner {suffix}",
        date_of_birth=datetime.date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
        must_change_password=False,
    )

    Scanner = apps.get_model(
        "organizing",
        "Scanner",
    )

    return Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_first_name="Amine",
        invited_last_name=(f"Scanner {suffix}"),
        invited_email=scanner_user.email,
        status=status,
        activated_at=(timezone.now() if status == "ACTIVE" else None),
    )


def make_event(
    *,
    organizer,
    suffix: str,
    status: str = Event.PUBLISHED,
):
    category = Category.objects.create(
        organizer=organizer,
        name=f"Football {suffix}",
        description="Football",
    )

    starts_at = timezone.now() + datetime.timedelta(days=10)

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Match {suffix}",
        description="Match test",
        starts_at=starts_at,
        ends_at=(starts_at + datetime.timedelta(hours=2)),
        venue="Stade FANID",
        capacity_total=100,
        status=status,
        published_at=(timezone.now() if status != Event.DRAFT else None),
    )


def client_for(
    user,
) -> APIClient:
    client = APIClient()

    client.force_authenticate(
        user=user,
    )

    return client


def collection_url(
    event: Event,
) -> str:
    return f"/api/v1/events/{event.pk}" "/scanners"


def detail_url(
    event: Event,
    scanner,
) -> str:
    return f"/api/v1/events/{event.pk}" f"/scanners/{scanner.pk}"


@pytest.mark.django_db
def test_draft_cannot_receive_scanner(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="draft",
    )

    event = make_event(
        organizer=organizer,
        suffix="draft",
        status=Event.DRAFT,
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="draft",
    )

    response = client_for(owner).post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert response.status_code == 409

    assert EventScannerAssignment.objects.count() == 0


@pytest.mark.django_db
def test_other_organizer_scanner_is_rejected(
    roles,
):
    owner_a, organizer_a = make_organizer(
        roles,
        suffix="cross-a",
    )

    owner_b, organizer_b = make_organizer(
        roles,
        suffix="cross-b",
    )

    event = make_event(
        organizer=organizer_a,
        suffix="cross",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer_b,
        owner=owner_b,
        suffix="cross",
    )

    response = client_for(owner_a).post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert response.status_code == 404

    assert EventScannerAssignment.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scanner_status",
    [
        "INVITED",
        "EMAIL_SENT",
        "OPENED",
        "ACTIVE",
    ],
)
def test_assignable_scanner_statuses(
    roles,
    scanner_status,
):
    suffix = "allowed-" + scanner_status.lower()

    owner, organizer = make_organizer(
        roles,
        suffix=suffix,
    )

    event = make_event(
        organizer=organizer,
        suffix=suffix,
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix=suffix,
        status=scanner_status,
    )

    response = client_for(owner).post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["scanner_id"] == str(scanner.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "scanner_status",
    [
        "LEAVE_REQUESTED",
        "INVITATION_CANCELLED",
        "DELETED",
    ],
)
def test_non_assignable_scanner_statuses(
    roles,
    scanner_status,
):
    suffix = "blocked-" + scanner_status.lower()

    owner, organizer = make_organizer(
        roles,
        suffix=suffix,
    )

    event = make_event(
        organizer=organizer,
        suffix=suffix,
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix=suffix,
        status=scanner_status,
    )

    response = client_for(owner).post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_many_scanners_per_event_and_many_events_per_scanner(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="many",
    )

    event_a = make_event(
        organizer=organizer,
        suffix="many-a",
    )

    event_b = make_event(
        organizer=organizer,
        suffix="many-b",
    )

    scanner_a = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="many-a",
        status="EMAIL_SENT",
    )

    scanner_b = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="many-b",
        status="ACTIVE",
    )

    client = client_for(owner)

    assert (
        client.post(
            collection_url(event_a),
            {
                "scanner_id": str(scanner_a.pk),
            },
            format="json",
        ).status_code
        == 201
    )

    assert (
        client.post(
            collection_url(event_a),
            {
                "scanner_id": str(scanner_b.pk),
            },
            format="json",
        ).status_code
        == 201
    )

    assert (
        client.post(
            collection_url(event_b),
            {
                "scanner_id": str(scanner_a.pk),
            },
            format="json",
        ).status_code
        == 201
    )

    event_a_response = client.get(collection_url(event_a))

    event_b_response = client.get(collection_url(event_b))

    assert event_a_response.status_code == 200
    assert event_b_response.status_code == 200

    assert {item["scanner_id"] for item in event_a_response.data} == {
        str(scanner_a.pk),
        str(scanner_b.pk),
    }

    assert {item["scanner_id"] for item in event_b_response.data} == {
        str(scanner_a.pk),
    }

    assert (
        EventScannerAssignment.objects.filter(
            unassigned_at__isnull=True,
        ).count()
        == 3
    )


@pytest.mark.django_db
def test_duplicate_assignment_is_idempotent(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="duplicate",
    )

    event = make_event(
        organizer=organizer,
        suffix="duplicate",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="duplicate",
    )

    client = client_for(owner)

    first = client.post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    second = client.post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert first.status_code == 201
    assert second.status_code == 200

    assert (
        EventScannerAssignment.objects.filter(
            event=event,
            scanner_id=scanner.pk,
            unassigned_at__isnull=True,
        ).count()
        == 1
    )

    assert (
        OutboxEvent.objects.filter(
            event_type=("catalog.event.scanner_assigned"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_unassign_then_reassign_keeps_history(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="history",
    )

    event = make_event(
        organizer=organizer,
        suffix="history",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="history",
    )

    client = client_for(owner)

    created = client.post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert created.status_code == 201

    removed = client.delete(
        detail_url(
            event,
            scanner,
        )
    )

    assert removed.status_code == 204

    old_assignment = EventScannerAssignment.objects.get(
        event=event,
        scanner_id=scanner.pk,
    )

    assert old_assignment.unassigned_at is not None

    assert old_assignment.unassigned_by_id == owner.pk

    recreated = client.post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert recreated.status_code == 201

    assert (
        EventScannerAssignment.objects.filter(
            event=event,
            scanner_id=scanner.pk,
        ).count()
        == 2
    )

    assert (
        EventScannerAssignment.objects.filter(
            event=event,
            scanner_id=scanner.pk,
            unassigned_at__isnull=True,
        ).count()
        == 1
    )

    assert (
        OutboxEvent.objects.filter(
            event_type=("catalog.event.scanner_unassigned"),
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_other_organizer_cannot_read_event_assignments(
    roles,
):
    owner_a, _ = make_organizer(
        roles,
        suffix="owner-a",
    )

    _, organizer_b = make_organizer(
        roles,
        suffix="owner-b",
    )

    event_b = make_event(
        organizer=organizer_b,
        suffix="foreign-event",
    )

    response = client_for(owner_a).get(collection_url(event_b))

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "terminal_status",
    [
        "INVITATION_CANCELLED",
        "DELETED",
    ],
)
def test_terminal_scanner_is_hidden_from_current_assignments(
    roles,
    terminal_status,
):
    owner, organizer = make_organizer(
        roles,
        suffix=("terminal-" + terminal_status.lower()),
    )

    event = make_event(
        organizer=organizer,
        suffix=("terminal-" + terminal_status.lower()),
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix=("terminal-" + terminal_status.lower()),
        status="ACTIVE",
    )

    client = client_for(owner)

    created = client.post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert created.status_code == 201

    assignment = EventScannerAssignment.objects.get(
        event=event,
        scanner_id=scanner.pk,
        unassigned_at__isnull=True,
    )

    scanner.__class__.objects.filter(
        pk=scanner.pk,
    ).update(
        status=terminal_status,
    )

    response = client.get(collection_url(event))

    assert response.status_code == 200

    assert all(item["scanner_id"] != str(scanner.pk) for item in response.data)

    assignment.refresh_from_db()

    assert assignment.unassigned_at is None


@pytest.mark.django_db
def test_archived_scanner_is_hidden_from_current_assignments(
    roles,
):
    owner, organizer = make_organizer(
        roles,
        suffix="archived-assignment",
    )

    event = make_event(
        organizer=organizer,
        suffix="archived-assignment",
    )

    scanner = make_scanner(
        roles,
        organizer=organizer,
        owner=owner,
        suffix="archived-assignment",
        status="ACTIVE",
    )

    client = client_for(owner)

    created = client.post(
        collection_url(event),
        {
            "scanner_id": str(scanner.pk),
        },
        format="json",
    )

    assert created.status_code == 201

    assignment = EventScannerAssignment.objects.get(
        event=event,
        scanner_id=scanner.pk,
        unassigned_at__isnull=True,
    )

    scanner.__class__.objects.filter(
        pk=scanner.pk,
    ).update(
        archived_at=scanner.created_at,
    )

    response = client.get(collection_url(event))

    assert response.status_code == 200

    assert all(item["scanner_id"] != str(scanner.pk) for item in response.data)

    assignment.refresh_from_db()

    assert assignment.unassigned_at is None
