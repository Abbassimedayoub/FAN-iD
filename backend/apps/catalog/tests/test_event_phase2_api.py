from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.events import AGGREGATE_EVENT, CATALOG_EVENT_PUBLISHED
from apps.catalog.models import Category, Event, TicketCategory
from apps.core.outbox.models import OutboxEvent

User = get_user_model()

APPROVED = "APPROVED"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(
        name="Phase 2B",
    )


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=f"phase2b-{suffix}@example.test",
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(
            1990,
            3,
            12,
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
        org_name=f"Organisation {suffix}",
        contact_email=(f"contact-{suffix}@example.test"),
        validation_status=APPROVED,
        commission_agreed_at=timezone.now(),
    )

    return user, organizer


def authenticate(
    client: APIClient,
    user,
) -> APIClient:
    client.force_authenticate(user=user)
    return client


def make_event(
    *,
    organizer,
    category,
    suffix: str,
    venue: str = "Stade FANID",
    capacity: int | None = 1000,
) -> Event:
    start = timezone.now() + datetime.timedelta(days=10)

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=f"Event {suffix}",
        description="Phase 2B",
        starts_at=start,
        ends_at=(start + datetime.timedelta(hours=3)),
        venue=venue,
        capacity_total=capacity,
    )


@pytest.mark.django_db
def test_event_api_accepts_venue_and_capacity(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="create-event",
    )

    start = timezone.now() + datetime.timedelta(days=10)

    response = authenticate(
        client,
        user,
    ).post(
        "/api/v1/events",
        {
            "category_id": str(category.pk),
            "name": "Match complet",
            "description": "Description",
            "starts_at": start.isoformat(),
            "ends_at": (start + datetime.timedelta(hours=2)).isoformat(),
            "venue": "Stade Vélodrome",
            "capacity_total": 65000,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["venue"] == ("Stade Vélodrome")
    assert response.data["capacity_total"] == 65000

    event = Event.objects.get(pk=response.data["id"])

    assert event.organizer_id == organizer.pk
    assert event.status == Event.DRAFT


@pytest.mark.django_db
def test_ticket_category_can_be_created_and_listed(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-create",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-create",
    )

    url = f"/api/v1/events/{event.pk}/" "ticket-categories"

    response = authenticate(
        client,
        user,
    ).post(
        url,
        {
            "name": "Tribune Honneur",
            "quota": 400,
            "unit_price_cents": 7500,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response["ETag"] == '"1"'
    assert response.data["sold_count"] == 0
    assert response.data["available_count"] == 400

    listed = client.get(url)

    assert listed.status_code == 200
    assert len(listed.data) == 1
    assert listed.data[0]["name"] == ("Tribune Honneur")


@pytest.mark.django_db
def test_ticket_quota_cannot_exceed_event_capacity(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="quota-capacity",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="quota-capacity",
        capacity=500,
    )

    TicketCategory.objects.create(
        event=event,
        name="A",
        quota=400,
        unit_price_cents=3000,
    )

    response = authenticate(
        client,
        user,
    ).post(
        (f"/api/v1/events/{event.pk}/" "ticket-categories"),
        {
            "name": "B",
            "quota": 101,
            "unit_price_cents": 3000,
        },
        format="json",
    )

    assert response.status_code == 400

    assert TicketCategory.objects.filter(event=event).count() == 1


@pytest.mark.django_db
def test_event_capacity_cannot_drop_below_quotas(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="capacity-update",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="capacity-update",
        capacity=1000,
    )

    TicketCategory.objects.create(
        event=event,
        name="Honneur",
        quota=600,
        unit_price_cents=3000,
    )

    response = authenticate(
        client,
        user,
    ).patch(
        f"/api/v1/events/{event.pk}",
        {
            "capacity_total": 500,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400

    event.refresh_from_db()

    assert event.capacity_total == 1000
    assert event.version == 1


@pytest.mark.django_db
def test_ticket_category_update_uses_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-update",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-update",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Virage",
        quota=300,
        unit_price_cents=2500,
    )

    url = f"/api/v1/events/{event.pk}/" f"ticket-categories/{ticket_category.pk}"

    response = authenticate(
        client,
        user,
    ).patch(
        url,
        {
            "quota": 350,
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["quota"] == 350
    assert response.data["version"] == 2


@pytest.mark.django_db
def test_ticket_category_update_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-if-match",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-if-match",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Virage",
        quota=300,
        unit_price_cents=2500,
    )

    response = authenticate(
        client,
        user,
    ).patch(
        (f"/api/v1/events/{event.pk}/" "ticket-categories/" f"{ticket_category.pk}"),
        {
            "quota": 350,
        },
        format="json",
    )

    assert response.status_code == 428


@pytest.mark.django_db
def test_foreign_ticket_categories_are_hidden(
    client,
    category,
    roles,
):
    user, _ = make_organizer(
        roles,
        suffix="ticket-reader",
    )

    _, foreign_organizer = make_organizer(
        roles,
        suffix="ticket-foreign",
    )

    event = make_event(
        organizer=foreign_organizer,
        category=category,
        suffix="ticket-foreign",
    )

    response = authenticate(
        client,
        user,
    ).get((f"/api/v1/events/{event.pk}/" "ticket-categories"))

    assert response.status_code == 404


@pytest.mark.django_db
def test_publish_requires_complete_business_data(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="publish-incomplete",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="publish-incomplete",
        venue="",
        capacity=None,
    )

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/publish",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 400

    event.refresh_from_db()

    assert event.status == Event.DRAFT
    assert event.published_at is None
    assert event.version == 1


@pytest.mark.django_db
def test_owner_can_publish_complete_event(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="publish",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="publish",
        capacity=1000,
    )

    TicketCategory.objects.create(
        event=event,
        name="Honneur",
        quota=600,
        unit_price_cents=5000,
    )

    TicketCategory.objects.create(
        event=event,
        name="Virage",
        quota=400,
        unit_price_cents=3000,
    )

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/publish",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["status"] == (Event.PUBLISHED)
    assert response.data["published_at"] is not None
    assert response.data["version"] == 2

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
    assert event.published_at is not None

    outbox_event = OutboxEvent.objects.get(
        event_type=CATALOG_EVENT_PUBLISHED,
        aggregate_type=AGGREGATE_EVENT,
        aggregate_id=event.pk,
    )

    assert outbox_event.event_version == 1
    assert outbox_event.actor_id == user.pk
    assert outbox_event.payload == {
        "status": Event.PUBLISHED,
    }


@pytest.mark.django_db
def test_publish_rejects_stale_version(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="publish-stale",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="publish-stale",
    )

    TicketCategory.objects.create(
        event=event,
        name="Honneur",
        quota=1000,
        unit_price_cents=5000,
    )

    Event.objects.filter(pk=event.pk).update(version=2)

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/publish",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    event.refresh_from_db()

    assert event.status == Event.DRAFT

    assert not OutboxEvent.objects.filter(
        event_type=CATALOG_EVENT_PUBLISHED,
        aggregate_type=AGGREGATE_EVENT,
        aggregate_id=event.pk,
    ).exists()


@pytest.mark.django_db
def test_published_event_cannot_be_structurally_edited(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="published-edit",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="published-edit",
    )

    event.status = Event.PUBLISHED
    event.published_at = timezone.now()
    event.save(
        update_fields=[
            "status",
            "published_at",
        ]
    )

    response = authenticate(
        client,
        user,
    ).patch(
        f"/api/v1/events/{event.pk}",
        {
            "venue": "Nouveau stade",
        },
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    event.refresh_from_db()

    assert event.venue == "Stade FANID"


@pytest.mark.django_db
def test_published_event_cannot_add_ticket_category(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="published-ticket",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="published-ticket",
    )

    event.status = Event.PUBLISHED
    event.published_at = timezone.now()
    event.save(
        update_fields=[
            "status",
            "published_at",
        ]
    )

    response = authenticate(
        client,
        user,
    ).post(
        (f"/api/v1/events/{event.pk}/" "ticket-categories"),
        {
            "name": "Nouvelle catégorie",
            "quota": 100,
            "unit_price_cents": 2000,
        },
        format="json",
    )

    assert response.status_code == 409
    assert TicketCategory.objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_ticket_category_can_be_deleted_in_draft(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-delete",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-delete",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="A supprimer",
        quota=200,
        unit_price_cents=2500,
    )

    response = authenticate(
        client,
        user,
    ).delete(
        (f"/api/v1/events/{event.pk}/" "ticket-categories/" f"{ticket_category.pk}"),
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 204

    assert not TicketCategory.objects.filter(pk=ticket_category.pk).exists()


@pytest.mark.django_db
def test_ticket_category_delete_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-delete-match",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-delete-match",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Sans match",
        quota=200,
        unit_price_cents=2500,
    )

    response = authenticate(
        client,
        user,
    ).delete((f"/api/v1/events/{event.pk}/" "ticket-categories/" f"{ticket_category.pk}"))

    assert response.status_code == 428

    assert TicketCategory.objects.filter(pk=ticket_category.pk).exists()


@pytest.mark.django_db
def test_ticket_category_delete_rejects_stale_version(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-delete-stale",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-delete-stale",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Stale",
        quota=200,
        unit_price_cents=2500,
    )

    TicketCategory.objects.filter(pk=ticket_category.pk).update(version=2)

    response = authenticate(
        client,
        user,
    ).delete(
        (f"/api/v1/events/{event.pk}/" "ticket-categories/" f"{ticket_category.pk}"),
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    assert TicketCategory.objects.filter(pk=ticket_category.pk).exists()


@pytest.mark.django_db
def test_ticket_category_with_sales_cannot_be_deleted(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="ticket-delete-sales",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="ticket-delete-sales",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Avec vente",
        quota=200,
        sold_count=1,
        unit_price_cents=2500,
    )

    response = authenticate(
        client,
        user,
    ).delete(
        (f"/api/v1/events/{event.pk}/" "ticket-categories/" f"{ticket_category.pk}"),
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    assert TicketCategory.objects.filter(pk=ticket_category.pk).exists()


@pytest.mark.django_db
def test_published_event_ticket_category_cannot_be_deleted(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="published-ticket-delete",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="published-ticket-delete",
    )

    ticket_category = TicketCategory.objects.create(
        event=event,
        name="Publiee",
        quota=200,
        unit_price_cents=2500,
    )

    event.status = Event.PUBLISHED
    event.published_at = timezone.now()

    event.save(
        update_fields=[
            "status",
            "published_at",
        ]
    )

    response = authenticate(
        client,
        user,
    ).delete(
        (f"/api/v1/events/{event.pk}/" "ticket-categories/" f"{ticket_category.pk}"),
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    assert TicketCategory.objects.filter(pk=ticket_category.pk).exists()


@pytest.mark.django_db
def test_owner_can_archive_published_event(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="archive",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="archive",
    )

    event.status = Event.PUBLISHED
    event.published_at = timezone.now()

    event.save(
        update_fields=[
            "status",
            "published_at",
        ]
    )

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/archive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 200
    assert response["ETag"] == '"2"'
    assert response.data["status"] == (Event.ARCHIVED)
    assert response.data["version"] == 2

    event.refresh_from_db()

    assert event.status == Event.ARCHIVED
    assert event.published_at is not None


@pytest.mark.django_db
def test_draft_event_cannot_be_archived(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="archive-draft",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="archive-draft",
    )

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/archive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    event.refresh_from_db()

    assert event.status == Event.DRAFT
    assert event.version == 1


@pytest.mark.django_db
def test_archive_requires_if_match(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="archive-match",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="archive-match",
    )

    event.status = Event.PUBLISHED
    event.published_at = timezone.now()

    event.save(
        update_fields=[
            "status",
            "published_at",
        ]
    )

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/archive",
        {},
        format="json",
    )

    assert response.status_code == 428

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
    assert event.version == 1


@pytest.mark.django_db
def test_archive_rejects_stale_version(
    client,
    category,
    roles,
):
    user, organizer = make_organizer(
        roles,
        suffix="archive-stale",
    )

    event = make_event(
        organizer=organizer,
        category=category,
        suffix="archive-stale",
    )

    Event.objects.filter(pk=event.pk).update(
        status=Event.PUBLISHED,
        published_at=timezone.now(),
        version=2,
    )

    response = authenticate(
        client,
        user,
    ).post(
        f"/api/v1/events/{event.pk}/archive",
        {},
        format="json",
        HTTP_IF_MATCH='"1"',
    )

    assert response.status_code == 409

    event.refresh_from_db()

    assert event.status == Event.PUBLISHED
    assert event.version == 2
