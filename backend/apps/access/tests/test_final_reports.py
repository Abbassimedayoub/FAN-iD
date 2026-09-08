from __future__ import annotations

import datetime

import pytest
from django.utils import timezone

from apps.access.models import EventFinalReport
from apps.access.services.final_reports import build_event_final_report
from apps.catalog.models import Category, Event
from apps.notifying.final_report_pdf import build_final_report_pdf
from apps.notifying.final_report_tasks import send_organizer_final_report_email
from apps.organizing.models import Organizer


class FakeSender:
    def __init__(self) -> None:
        self.emails_sent = []

    def send_email(self, **kwargs) -> None:
        self.emails_sent.append(kwargs)


@pytest.fixture
def final_report(django_user_model, roles):
    now = timezone.now()
    owner = django_user_model.objects.create_user(
        email="final-report-owner@example.test",
        password="testpassword123",
        first_name="Amina",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=now,
        role=roles["FAN"],
    )
    organizer = Organizer.objects.create(
        user=owner,
        org_name="Organizer final report",
        contact_email="reports@example.test",
    )
    category = Category.objects.create(name="Final report category")
    event = Event.objects.create(
        organizer=organizer,
        category=category,
        name="Événement terminé",
        status=Event.COMPLETED,
        starts_at=now - datetime.timedelta(hours=3),
        ends_at=now - datetime.timedelta(hours=1),
    )
    return EventFinalReport.objects.create(
        event=event,
        generated_at=now,
        tickets_sold_count=20,
        tickets_used_count=15,
        tickets_voided_count=2,
        tickets_absent_count=3,
        gross_revenue_cents=50000,
        refunds_cents=10000,
        net_revenue_cents=40000,
        commission_rate="0.1000",
        commission_cents=4000,
        organizer_net_cents=36000,
        scanner_stats=[],
    )


@pytest.mark.django_db
def test_final_report_pdf_is_valid(final_report):
    pdf = build_final_report_pdf(report=final_report)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


@pytest.mark.django_db
def test_final_report_email_attaches_pdf(final_report, monkeypatch):
    sender = FakeSender()
    monkeypatch.setattr(
        "apps.notifying.final_report_tasks.build_notification_sender",
        lambda: sender,
    )

    result = send_organizer_final_report_email.run(
        event_id=str(final_report.event_id),
    )

    assert result["sent"] is True
    attachment = sender.emails_sent[0]["attachments"][0]
    assert attachment[0].endswith(".pdf")
    assert attachment[1].startswith(b"%PDF")
    assert attachment[2] == "application/pdf"


@pytest.mark.django_db
def test_final_report_snapshot_can_lock_completed_event(final_report):
    EventFinalReport.objects.filter(pk=final_report.pk).delete()

    rebuilt = build_event_final_report(event_id=final_report.event_id)

    assert rebuilt.event_id == final_report.event_id
    assert rebuilt.tickets_sold_count == 0
