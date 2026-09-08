from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.catalog.models import Category, Event, TicketCategory
from apps.notifying.event_buyer_consumers import EventBuyerNotificationConsumer
from apps.notifying.event_buyer_tasks import send_event_buyer_postponement_emails
from apps.ordering.services.confirmation import confirm_order_payment
from apps.ordering.services.reservations import ReservationLine, reserve_stock
from apps.organizing.models import Organizer


class FakeSender:
    def __init__(self):
        self.emails_sent = []

    def send_email(self, *, to, subject, body, **kwargs):
        self.emails_sent.append(
            {"to": to, "subject": subject, "body": body}
        )


@pytest.mark.django_db
def test_postponement_email_notifies_each_buyer_once(
    django_user_model,
    roles,
    monkeypatch,
):
    owner = django_user_model.objects.create_user(
        email="notify-owner@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )
    organizer = Organizer.objects.create(
        user=owner,
        org_name="Notification organization",
        contact_email="notify-organizer@example.test",
    )
    category = Category.objects.create(name="Notification category")
    old_start = timezone.now() + datetime.timedelta(days=7)
    new_start = old_start + datetime.timedelta(days=14)
    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Événement reporté acheteurs",
        status=Event.POSTPONED,
        published_at=timezone.now(),
        starts_at=new_start,
        ends_at=new_start + datetime.timedelta(hours=2),
        postponed_from_starts_at=old_start,
        postponed_from_ends_at=old_start + datetime.timedelta(hours=2),
        postponed_to_starts_at=new_start,
        postponed_to_ends_at=new_start + datetime.timedelta(hours=2),
        lifecycle_reason="Conditions météorologiques.",
        capacity_total=20,
    )
    tariff = TicketCategory.objects.create(
        event=event,
        name="Standard",
        quota=20,
        unit_price_cents=1200,
    )
    buyer = django_user_model.objects.create_user(
        email="notify-buyer@example.test",
        password="testpassword123",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["FAN"],
    )
    order = reserve_stock(
        user=buyer,
        lines=[ReservationLine(tariff.id, 2)],
    )
    confirm_order_payment(order_id=order.id)

    sender = FakeSender()
    monkeypatch.setattr(
        "apps.notifying.event_buyer_tasks.build_notification_sender",
        lambda: sender,
    )

    result = send_event_buyer_postponement_emails.run(
        event_id=str(event.id),
    )

    assert result == {"sent": True, "recipients": 1}
    assert len(sender.emails_sent) == 1
    assert sender.emails_sent[0]["to"] == buyer.email
    assert "restent valides" in sender.emails_sent[0]["body"]


def test_consumer_respects_notify_buyers(monkeypatch):
    deferred = []
    consumer = EventBuyerNotificationConsumer()

    monkeypatch.setattr(
        "apps.notifying.event_buyer_consumers."
        "send_event_buyer_postponement_emails.delay",
        lambda **kwargs: deferred.append(kwargs),
    )
    monkeypatch.setattr(
        consumer,
        "defer",
        lambda callback: callback(),
    )

    consumer.handle(
        SimpleNamespace(
            aggregate_id="00000000-0000-0000-0000-000000000001",
            payload={"notify_buyers": False},
        )
    )
    assert deferred == []

    consumer.handle(
        SimpleNamespace(
            aggregate_id="00000000-0000-0000-0000-000000000001",
            payload={"notify_buyers": True},
        )
    )
    assert deferred == [
        {"event_id": "00000000-0000-0000-0000-000000000001"}
    ]



def test_refund_email_consumer_schedules_after_success(monkeypatch):
    from apps.notifying.refund_notification_consumers import (
        PaymentRefundNotificationConsumer,
    )

    scheduled = []
    consumer = PaymentRefundNotificationConsumer()

    monkeypatch.setattr(
        "apps.notifying.refund_notification_consumers."
        "send_refund_succeeded_email.delay",
        lambda **kwargs: scheduled.append(kwargs),
    )
    monkeypatch.setattr(consumer, "defer", lambda callback: callback())

    consumer.handle(
        SimpleNamespace(
            aggregate_id="00000000-0000-0000-0000-000000000001",
        )
    )

    assert scheduled == [
        {"refund_id": "00000000-0000-0000-0000-000000000001"},
    ]
