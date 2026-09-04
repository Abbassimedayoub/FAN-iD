from __future__ import annotations

import datetime

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event, TicketCategory

User = get_user_model()

CATEGORIES_URL = "/api/v1/catalog/categories"
EVENTS_URL = "/api/v1/catalog/events"

ORGANIZER_APPROVED = "APPROVED"
ORGANIZER_SUSPENDED = "SUSPENDED"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def make_organizer(
    roles,
    *,
    suffix: str,
):
    user = User.objects.create_user(
        email=f"fan-catalog-{suffix}@example.test",
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

    return Organizer.objects.create(
        user=user,
        org_name=f"Catalogue {suffix}",
        contact_email=f"catalogue-{suffix}@example.test",
        validation_status=ORGANIZER_APPROVED,
        commission_agreed_at=timezone.now(),
    )


def create_event(
    *,
    organizer,
    category: Category,
    name: str,
    event_status: str,
    days: int,
) -> Event:
    starts_at = timezone.now() + datetime.timedelta(
        days=days,
    )

    return Event.objects.create(
        organizer=organizer,
        category=category,
        name=name,
        description=f"Description {name}",
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        venue="Stade FANID",
        capacity_total=1000,
        status=event_status,
        published_at=(timezone.now() if event_status != Event.DRAFT else None),
        lifecycle_reason=(
            f"Reason {event_status}"
            if event_status
            in {
                Event.POSTPONED,
                Event.SUSPENDED,
                Event.CANCELLED,
            }
            else ""
        ),
    )


@pytest.mark.django_db
def test_fan_catalog_lists_categories_without_status_filter(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="categories",
    )

    empty_category = Category.objects.create(
        name="Catégorie vide",
    )

    categories = []

    for index, event_status in enumerate(
        Event.STATUSES,
        start=1,
    ):
        category = Category.objects.create(
            name=f"Catégorie {event_status}",
        )
        categories.append(category)

        create_event(
            organizer=organizer,
            category=category,
            name=f"Event {event_status}",
            event_status=event_status,
            days=index,
        )

    response = client.get(CATEGORIES_URL)

    assert response.status_code == 200

    returned_ids = {item["id"] for item in response.data}

    assert returned_ids == {
        str(empty_category.pk),
        *{str(category.pk) for category in categories},
    }

    for item in response.data:
        assert set(item) == {
            "id",
            "name",
            "description",
        }


@pytest.mark.django_db
def test_fan_catalog_events_hide_archived_and_keep_other_statuses(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="statuses",
    )

    category = Category.objects.create(
        name="Tous les statuts",
    )

    created = []

    for index, event_status in enumerate(
        Event.STATUSES,
        start=1,
    ):
        event = create_event(
            organizer=organizer,
            category=category,
            name=f"Event {event_status}",
            event_status=event_status,
            days=index,
        )
        created.append(event)

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200

    visible_statuses = set(Event.STATUSES) - {
        Event.ARCHIVED,
    }

    assert response.data["count"] == len(visible_statuses)

    returned_ids = {item["id"] for item in response.data["results"]}

    assert returned_ids == {str(event.pk) for event in created if event.status != Event.ARCHIVED}

    assert {item["status"] for item in response.data["results"]} == visible_statuses

    assert Event.ARCHIVED not in {item["status"] for item in response.data["results"]}


@pytest.mark.django_db
def test_fan_catalog_hides_events_of_suspended_organizer(
    client,
    roles,
):
    suspended_organizer = make_organizer(
        roles,
        suffix="suspended-hidden",
    )
    approved_organizer = make_organizer(
        roles,
        suffix="approved-visible",
    )

    category = Category.objects.create(
        name="Suspension organizer",
    )

    hidden_event = create_event(
        organizer=suspended_organizer,
        category=category,
        name="Event organizer suspendu",
        event_status=Event.PUBLISHED,
        days=1,
    )

    visible_event = create_event(
        organizer=approved_organizer,
        category=category,
        name="Event organizer approuve",
        event_status=Event.PUBLISHED,
        days=2,
    )

    suspended_organizer.validation_status = ORGANIZER_SUSPENDED
    suspended_organizer.save(
        update_fields=[
            "validation_status",
            "updated_at",
        ]
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert [item["id"] for item in response.data["results"]] == [
        str(visible_event.pk)
    ]
    assert str(hidden_event.pk) not in {
        item["id"] for item in response.data["results"]
    }


@pytest.mark.django_db
def test_fan_catalog_events_are_filtered_only_by_category(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="category-filter",
    )

    wanted_category = Category.objects.create(
        name="Football",
    )
    other_category = Category.objects.create(
        name="Concert",
    )

    wanted = create_event(
        organizer=organizer,
        category=wanted_category,
        name="Football draft",
        event_status=Event.DRAFT,
        days=1,
    )

    create_event(
        organizer=organizer,
        category=other_category,
        name="Concert published",
        event_status=Event.PUBLISHED,
        days=2,
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(wanted_category.pk),
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(wanted.pk)
    assert response.data["results"][0]["status"] == Event.DRAFT


@pytest.mark.django_db
def test_fan_catalog_exposes_available_price_summary(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="pricing",
    )

    category = Category.objects.create(
        name="Pricing",
    )

    event = create_event(
        organizer=organizer,
        category=category,
        name="Event pricing",
        event_status=Event.PUBLISHED,
        days=1,
    )

    TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=100,
        sold_count=0,
        unit_price_cents=2500,
    )

    TicketCategory.objects.create(
        event=event,
        name="Early",
        quota=20,
        sold_count=5,
        unit_price_cents=1500,
    )

    TicketCategory.objects.create(
        event=event,
        name="Epuisé",
        quota=10,
        sold_count=10,
        unit_price_cents=500,
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200

    item = response.data["results"][0]

    assert item["ticket_category_count"] == 3
    assert item["available_ticket_category_count"] == 2

    # Le tarif épuisé à 5 EUR ne doit pas devenir
    # le prix d'appel affiché au Fan.
    assert item["min_price_cents"] == 1500


@pytest.mark.django_db
def test_fan_catalog_exposes_status_details_without_organizer(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="details",
    )

    category = Category.objects.create(
        name="Lifecycle details",
    )

    event = create_event(
        organizer=organizer,
        category=category,
        name="Event suspendu",
        event_status=Event.SUSPENDED,
        days=1,
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200

    item = response.data["results"][0]

    expected_fields = {
        "id",
        "category_id",
        "name",
        "description",
        "starts_at",
        "ends_at",
        "postponed_from_starts_at",
        "postponed_from_ends_at",
        "postponed_to_starts_at",
        "postponed_to_ends_at",
        "venue",
        "capacity_total",
        "image_url",
        "min_price_cents",
        "ticket_category_count",
        "available_ticket_category_count",
        "ticket_categories",
        "can_add_to_cart",
        "status",
        "published_at",
        "lifecycle_reason",
        "lifecycle_changed_at",
    }

    assert set(item) == expected_fields
    assert item["status"] == Event.SUSPENDED
    assert item["min_price_cents"] is None
    assert item["ticket_category_count"] == 0
    assert item["available_ticket_category_count"] == 0
    assert item["ticket_categories"] == []
    assert item["can_add_to_cart"] is False

    assert item["lifecycle_reason"] == (
        Event.objects.get(
            pk=event.pk,
        ).lifecycle_reason
    )

    assert "organizer_id" not in item
    assert "version" not in item
    assert "created_at" not in item
    assert "updated_at" not in item


@pytest.mark.django_db
def test_fan_catalog_accepts_legacy_event_without_organizer(
    client,
):
    category = Category.objects.create(
        name="Legacy",
    )

    starts_at = timezone.now() + datetime.timedelta(
        days=1,
    )

    event = Event.objects.create(
        organizer=None,
        category=category,
        name="Legacy draft",
        starts_at=starts_at,
        ends_at=starts_at + datetime.timedelta(hours=2),
        status=Event.DRAFT,
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["id"] == str(event.pk)


@pytest.mark.django_db
def test_fan_catalog_event_list_requires_valid_category_id(
    client,
):
    missing = client.get(EVENTS_URL)

    assert missing.status_code == 400

    invalid = client.get(
        EVENTS_URL,
        {
            "category_id": "not-a-uuid",
        },
    )

    assert invalid.status_code == 400


@pytest.mark.django_db
def test_fan_catalog_event_list_uses_standard_pagination(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="pagination",
    )

    category = Category.objects.create(
        name="Pagination",
    )

    for index in range(3):
        create_event(
            organizer=organizer,
            category=category,
            name=f"Event {index}",
            event_status=Event.PUBLISHED,
            days=index + 1,
        )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 3
    assert len(response.data["results"]) == 1


@pytest.mark.django_db
def test_fan_catalog_is_read_only(
    client,
):
    categories_response = client.post(
        CATEGORIES_URL,
        {
            "name": "Interdite",
        },
        format="json",
    )

    events_response = client.post(
        EVENTS_URL,
        {},
        format="json",
    )

    assert categories_response.status_code == 405
    assert events_response.status_code == 405


@pytest.mark.django_db
def test_fan_catalog_exposes_cart_ticket_categories(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="cart-tariffs",
    )

    category = Category.objects.create(
        name="Cart tariffs",
    )

    event = create_event(
        organizer=organizer,
        category=category,
        name="Cart tariffs event",
        event_status=Event.PUBLISHED,
        days=1,
    )

    expensive = TicketCategory.objects.create(
        event=event,
        name="VIP",
        quota=10,
        sold_count=2,
        unit_price_cents=5000,
    )

    cheap = TicketCategory.objects.create(
        event=event,
        name="Virage",
        quota=30,
        sold_count=5,
        unit_price_cents=4000,
    )

    sold_out = TicketCategory.objects.create(
        event=event,
        name="Early",
        quota=2,
        sold_count=2,
        unit_price_cents=1000,
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200

    item = response.data["results"][0]

    assert item["can_add_to_cart"] is True

    assert item["ticket_categories"] == [
        {
            "id": str(sold_out.pk),
            "name": "Early",
            "unit_price_cents": 1000,
            "available_count": 0,
        },
        {
            "id": str(cheap.pk),
            "name": "Virage",
            "unit_price_cents": 4000,
            "available_count": 25,
        },
        {
            "id": str(expensive.pk),
            "name": "VIP",
            "unit_price_cents": 5000,
            "available_count": 8,
        },
    ]


@pytest.mark.django_db
def test_fan_catalog_cart_eligibility_respects_lifecycle(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="cart-lifecycle",
    )

    category = Category.objects.create(
        name="Cart lifecycle",
    )

    expected = {}

    for index, event_status in enumerate(
        (
            Event.PUBLISHED,
            Event.POSTPONED,
            Event.DRAFT,
            Event.SUSPENDED,
            Event.CANCELLED,
        ),
        start=1,
    ):
        event = create_event(
            organizer=organizer,
            category=category,
            name=f"Cart {event_status}",
            event_status=event_status,
            days=index,
        )

        TicketCategory.objects.create(
            event=event,
            name="Standard",
            quota=5,
            sold_count=0,
            unit_price_cents=2500,
        )

        expected[str(event.pk)] = event_status in {
            Event.PUBLISHED,
            Event.POSTPONED,
        }

        if event_status == Event.POSTPONED:
            assert event.postponed_to_starts_at is None
            assert event.postponed_to_ends_at is None

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200

    items = {
        item["id"]: item
        for item in response.data["results"]
    }

    assert set(items) == set(expected)

    for event_id, can_add in expected.items():
        assert items[event_id]["can_add_to_cart"] is can_add


@pytest.mark.django_db
def test_fan_catalog_cart_rejects_fully_sold_out_event(
    client,
    roles,
):
    organizer = make_organizer(
        roles,
        suffix="cart-full",
    )

    category = Category.objects.create(
        name="Cart full",
    )

    event = create_event(
        organizer=organizer,
        category=category,
        name="Sold out event",
        event_status=Event.PUBLISHED,
        days=1,
    )

    TicketCategory.objects.create(
        event=event,
        name="Complet",
        quota=3,
        sold_count=3,
        unit_price_cents=3000,
    )

    response = client.get(
        EVENTS_URL,
        {
            "category_id": str(category.pk),
        },
    )

    assert response.status_code == 200

    item = response.data["results"][0]

    assert item["can_add_to_cart"] is False
    assert item["available_ticket_category_count"] == 0
    assert item["ticket_categories"][0]["available_count"] == 0
