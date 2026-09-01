from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.adapters.notifications import (
    InMemorySender,
)
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_SUSPENDED,
)
from apps.organizing.models import (
    Organizer,
    OrganizerReactivationRequest,
)
from apps.organizing.reactivation_service import (
    OrganizerReactivationService,
)
from apps.organizing.reactivation_tasks import (
    send_reactivation_decision_emails,
    send_reactivation_requested_emails,
)

User = get_user_model()

PASSWORD = "Organisateur-Solide-2026!"


def make_owner(
    roles,
    *,
    suffix: str,
):
    owner = User.objects.create_user(
        email=f"reactivation-{suffix}@example.test",
        password=PASSWORD,
        first_name="Nadia",
        last_name="Benali",
        date_of_birth=datetime.date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name=f"Reactivation Org {suffix}",
        contact_email=(f"reactivation-contact-{suffix}@example.test"),
        validation_status=ORGANIZER_SUSPENDED,
    )

    return owner, organizer


def make_admin(
    roles,
    *,
    suffix: str,
):
    return User.objects.create_user(
        email=f"admin-reactivation-{suffix}@example.test",
        password=PASSWORD,
        first_name="Admin",
        last_name="FANID",
        date_of_birth=datetime.date(
            1985,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles["ADMIN"],
    )


@pytest.mark.django_db
def test_suspended_organizer_requests_reactivation_but_stays_suspended(
    roles,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    owner, organizer = make_owner(
        roles,
        suffix="request",
    )

    calls = []

    monkeypatch.setattr(
        send_reactivation_requested_emails,
        "delay",
        lambda **kwargs: calls.append(kwargs),
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        response = client.post(
            "/api/v1/organizers/me/reactivation-request",
            {},
            format="json",
        )

    assert response.status_code == 201
    assert response.data["status"] == "PENDING"

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_SUSPENDED

    request = OrganizerReactivationRequest.objects.get(
        organizer=organizer,
    )

    assert request.requested_by_id == owner.pk
    assert request.status == "PENDING"
    assert request.organizer_version == organizer.version
    assert calls == [
        {
            "request_id": str(request.pk),
        }
    ]


@pytest.mark.django_db
def test_duplicate_pending_request_is_idempotent(
    roles,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    owner, organizer = make_owner(
        roles,
        suffix="duplicate",
    )

    calls = []

    monkeypatch.setattr(
        send_reactivation_requested_emails,
        "delay",
        lambda **kwargs: calls.append(kwargs),
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    with django_capture_on_commit_callbacks(
        execute=True,
    ):
        first = client.post(
            "/api/v1/organizers/me/reactivation-request",
            {},
            format="json",
        )

        second = client.post(
            "/api/v1/organizers/me/reactivation-request",
            {},
            format="json",
        )

    assert first.status_code == 201
    assert second.status_code == 200

    assert first.data["id"] == second.data["id"]

    assert (
        OrganizerReactivationRequest.objects.filter(
            organizer=organizer,
            status="PENDING",
        ).count()
        == 1
    )

    assert len(calls) == 1


@pytest.mark.django_db
def test_non_suspended_organizer_cannot_request_reactivation(
    roles,
):
    owner, organizer = make_owner(
        roles,
        suffix="approved",
    )

    organizer.validation_status = ORGANIZER_APPROVED
    organizer.save(
        update_fields=[
            "validation_status",
        ]
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        "/api/v1/organizers/me/reactivation-request",
        {},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "ORGANIZER_REACTIVATION_NOT_ALLOWED"


@pytest.mark.django_db
def test_old_self_reopen_endpoint_no_longer_exists(
    roles,
):
    owner, organizer = make_owner(
        roles,
        suffix="legacy-route",
    )

    client = APIClient()
    client.force_authenticate(user=owner)

    response = client.post(
        "/api/v1/organizers/me/reopen",
        {},
        format="json",
        HTTP_IF_MATCH=f'"{organizer.version}"',
    )

    assert response.status_code == 404

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_SUSPENDED


@pytest.mark.django_db
def test_admin_approval_requires_step_up_otp(
    roles,
    monkeypatch,
):
    owner, organizer = make_owner(
        roles,
        suffix="otp",
    )
    admin = make_admin(
        roles,
        suffix="otp",
    )

    monkeypatch.setattr(
        send_reactivation_requested_emails,
        "delay",
        lambda **kwargs: None,
    )

    OrganizerReactivationService.request(
        organizer_id=organizer.pk,
        requested_by_id=owner.pk,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    response = client.post(
        (f"/api/v1/admin/organizers/" f"{organizer.pk}/reactivation-request/approve"),
        {},
        format="json",
        HTTP_IF_MATCH=f'"{organizer.version}"',
    )

    assert response.status_code == 403

    assert response.data["error"]["code"] == "STEP_UP_REQUIRED"

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_SUSPENDED


@pytest.mark.django_db
def test_only_admin_service_decision_reopens_after_pending_request(
    roles,
    monkeypatch,
):
    owner, organizer = make_owner(
        roles,
        suffix="approve",
    )
    admin = make_admin(
        roles,
        suffix="approve",
    )

    monkeypatch.setattr(
        send_reactivation_requested_emails,
        "delay",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        send_reactivation_decision_emails,
        "delay",
        lambda **kwargs: None,
    )

    request, created = OrganizerReactivationService.request(
        organizer_id=organizer.pk,
        requested_by_id=owner.pk,
    )

    assert created is True

    request, reopened = OrganizerReactivationService.approve(
        organizer_id=organizer.pk,
        reviewed_by_id=admin.pk,
        expected_version=organizer.version,
    )

    reopened.refresh_from_db()
    request.refresh_from_db()

    assert reopened.validation_status == ORGANIZER_APPROVED
    assert request.status == "APPROVED"
    assert request.reviewed_by_id == admin.pk
    assert request.reviewed_at is not None


@pytest.mark.django_db
def test_admin_rejection_keeps_organizer_suspended(
    roles,
    monkeypatch,
):
    owner, organizer = make_owner(
        roles,
        suffix="reject",
    )
    admin = make_admin(
        roles,
        suffix="reject",
    )

    monkeypatch.setattr(
        send_reactivation_requested_emails,
        "delay",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        send_reactivation_decision_emails,
        "delay",
        lambda **kwargs: None,
    )

    request, _ = OrganizerReactivationService.request(
        organizer_id=organizer.pk,
        requested_by_id=owner.pk,
    )

    request = OrganizerReactivationService.reject(
        organizer_id=organizer.pk,
        reviewed_by_id=admin.pk,
        expected_version=organizer.version,
        reason="Vérification complémentaire requise.",
    )

    organizer.refresh_from_db()
    request.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_SUSPENDED
    assert request.status == "REJECTED"
    assert request.reviewed_by_id == admin.pk
    assert request.rejection_reason == "Vérification complémentaire requise."


@pytest.mark.django_db
def test_request_and_decision_emails_are_traceable(
    roles,
    monkeypatch,
):
    owner, organizer = make_owner(
        roles,
        suffix="emails",
    )
    admin = make_admin(
        roles,
        suffix="emails",
    )

    request = OrganizerReactivationRequest.objects.create(
        organizer=organizer,
        requested_by=owner,
        organizer_version=organizer.version,
    )

    sender = InMemorySender()

    monkeypatch.setattr(
        ("apps.organizing.reactivation_tasks." "build_notification_sender"),
        lambda: sender,
    )

    result = send_reactivation_requested_emails.run(
        request_id=str(request.pk),
    )

    assert result["sent"] is True

    recipients = {item["to"] for item in sender.emails_sent}

    assert owner.email in recipients
    assert organizer.contact_email in recipients
    assert admin.email in recipients

    request.refresh_from_db()

    assert request.request_organizer_email_sent_at is not None
    assert request.request_admin_email_sent_at is not None

    sender.emails_sent.clear()

    request.status = "APPROVED"
    request.reviewed_by = admin
    request.reviewed_at = timezone.now()
    request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )

    result = send_reactivation_decision_emails.run(
        request_id=str(request.pk),
    )

    assert result["sent"] is True
    assert result["decision"] == "APPROVED"

    recipients = {item["to"] for item in sender.emails_sent}

    assert owner.email in recipients
    assert admin.email in recipients

    request.refresh_from_db()

    assert request.decision_organizer_email_sent_at is not None
    assert request.decision_admin_email_sent_at is not None
