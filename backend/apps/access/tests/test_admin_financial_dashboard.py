from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from apps.access.models import EventFinalReport
from apps.catalog.models import Category, Event
from apps.organizing.models import Organizer


@pytest.mark.django_db
def test_admin_reads_confirmed_commission_and_organizer_net_revenue(
    django_user_model,
    roles,
):
    now = timezone.now()
    admin = django_user_model.objects.create_user(
        email="financial-admin@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["ADMIN"],
    )
    owner = django_user_model.objects.create_user(
        email="financial-owner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    organizer = Organizer.objects.create(
        user=owner,
        org_name="Organizer rentable",
        contact_email="financial-organizer@example.test",
    )
    event = Event.objects.create(
        organizer=organizer,
        category=Category.objects.create(name="Financial category"),
        name="Événement finalisé",
        status=Event.COMPLETED,
        starts_at=now - datetime.timedelta(hours=3),
        ends_at=now - datetime.timedelta(hours=1),
    )
    EventFinalReport.objects.create(
        event=event,
        generated_at=now,
        tickets_sold_count=10,
        tickets_used_count=8,
        tickets_voided_count=1,
        tickets_absent_count=1,
        gross_revenue_cents=12000,
        refunds_cents=2000,
        net_revenue_cents=10000,
        commission_rate=Decimal("0.1000"),
        commission_cents=1000,
        organizer_net_cents=9000,
        scanner_stats=[],
    )

    client = Client()
    client.force_login(admin)
    response = client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200, response.content
    assert response.json() == {
        "confirmed_commission_cents": 1000,
        "organizer_count": 1,
        "organizers": [
            {
                "organizer_id": str(organizer.id),
                "org_name": "Organizer rentable",
                "net_revenue_cents": 10000,
                "completed_events_count": 1,
            }
        ],
    }


@pytest.mark.django_db
def test_non_admin_cannot_read_financial_dashboard(
    django_user_model,
    roles,
):
    user = django_user_model.objects.create_user(
        email="financial-fan@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )
    client = Client()
    client.force_login(user)

    assert client.get("/api/v1/admin/dashboard").status_code == 403
