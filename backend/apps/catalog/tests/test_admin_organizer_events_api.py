from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.catalog.models import Category, Event, TicketCategory
from apps.catalog.views import AdminOrganizerEventListView

User = get_user_model()


def make_admin(
    roles,
):
    return User.objects.create_user(
        email="catalog-admin@example.test",
        password="Test-password-2026!",
        first_name="Admin",
        last_name="FANID",
        date_of_birth=date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ADMIN"],
    )


def make_organizer(
    roles,
    *,
    suffix: str,
):
    owner = User.objects.create_user(
        email=(f"owner-{suffix}@example.test"),
        password="Test-password-2026!",
        first_name="Owner",
        last_name="FANID",
        date_of_birth=date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer_model = Event._meta.get_field("organizer").remote_field.model

    organizer = organizer_model.objects.create(
        user=owner,
        org_name=f"Organizer {suffix}",
        validation_status="APPROVED",
        contact_email=owner.email,
        commission_rate="0.1000",
    )

    return organizer


@pytest.mark.django_db
def test_admin_reads_event_ticket_sales(
    roles,
):
    admin = make_admin(roles)

    organizer = make_organizer(
        roles,
        suffix="sales",
    )

    other_organizer = make_organizer(
        roles,
        suffix="other",
    )

    category = Category.objects.create(
        name="Football Admin Sales",
        description="",
    )

    now = timezone.now()

    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Finale FANID",
        description="",
        starts_at=(now + timedelta(days=20)),
        ends_at=(
            now
            + timedelta(
                days=20,
                hours=2,
            )
        ),
        venue="Stade FANID",
        capacity_total=75,
        status=Event.PUBLISHED,
    )

    TicketCategory.objects.create(
        event=event,
        name="VIP",
        quota=50,
        sold_count=48,
        unit_price_cents=2500,
    )

    TicketCategory.objects.create(
        event=event,
        name="Virage",
        quota=25,
        sold_count=22,
        unit_price_cents=1500,
    )

    other_event = Event.objects.create(
        organizer=other_organizer,
        category=category,
        name="Autre événement",
        description="",
        starts_at=(now + timedelta(days=30)),
        ends_at=(
            now
            + timedelta(
                days=30,
                hours=2,
            )
        ),
        venue="Autre stade",
        capacity_total=10,
        status=Event.PUBLISHED,
    )

    path = "/api/v1/admin/organizers/" f"{organizer.pk}/events"

    match = resolve(path)

    assert match.func.view_class is AdminOrganizerEventListView

    factory = APIRequestFactory()

    request = factory.get(path)

    force_authenticate(
        request,
        user=admin,
    )

    # Même niveau que la consultation de la
    # fiche organizer côté administration.
    request.auth_level = 1

    response = AdminOrganizerEventListView.as_view()(
        request,
        organizer_id=organizer.pk,
    )

    assert response.status_code == 200, response.data

    results = response.data.get(
        "results",
        response.data,
    )

    assert len(results) == 1

    item = results[0]

    assert item["id"] == str(event.pk)
    assert item["name"] == "Finale FANID"

    tickets = item["ticket_categories"]

    assert [
        {
            "name": ticket["name"],
            "sold_count": (ticket["sold_count"]),
            "quota": ticket["quota"],
            "unit_price_cents": (ticket["unit_price_cents"]),
        }
        for ticket in tickets
    ] == [
        {
            "name": "VIP",
            "sold_count": 48,
            "quota": 50,
            "unit_price_cents": 2500,
        },
        {
            "name": "Virage",
            "sold_count": 22,
            "quota": 25,
            "unit_price_cents": 1500,
        },
    ]

    ids = {item["id"] for item in results}

    assert str(other_event.pk) not in ids


@pytest.mark.django_db
def test_admin_event_sales_surface_is_read_only():
    assert "post" not in AdminOrganizerEventListView.__dict__
    assert "patch" not in AdminOrganizerEventListView.__dict__
    assert "put" not in AdminOrganizerEventListView.__dict__
    assert "delete" not in AdminOrganizerEventListView.__dict__
