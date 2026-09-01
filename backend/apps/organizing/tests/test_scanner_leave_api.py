from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    SCANNER_ACTIVE,
    SCANNER_DELETED,
    SCANNER_LEAVE_REQUESTED,
)
from apps.organizing.models import Organizer, Scanner, ScannerRevocationChallenge
from apps.organizing.scanner_security import (
    SCANNER_SECURITY_ACTION_LEAVE_ACCEPT,
    SCANNER_SECURITY_ACTION_LEAVE_REQUEST,
    ScannerSecurityService,
    derive_scanner_security_code,
)
from apps.organizing.scanner_security_tasks import send_scanner_security_code_email
from apps.organizing.services.scanner_leaves import ScannerLeaveService

User = get_user_model()

REQUEST_URL = "/api/v1/organizers/" "scanner-leave/request"

SECURITY_URL = "/api/v1/organizers/" "scanner-leave/security-code"


@pytest.fixture(autouse=True)
def disable_security_email_dispatch(
    monkeypatch,
):
    monkeypatch.setattr(
        "apps.organizing." "scanner_security_tasks." "send_scanner_security_code_email.delay",
        lambda **kwargs: None,
    )


def make_user(
    *,
    email,
    role,
):
    return User.objects.create_user(
        email=email,
        password="Strong-Test-Password-2026!",
        first_name="Test",
        last_name="User",
        date_of_birth=datetime.date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=role,
    )


def make_context(
    *,
    roles,
    suffix,
):
    owner = make_user(
        email=(f"leave-owner-{suffix}@example.test"),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name=f"Leave Org {suffix}",
        contact_email=(f"leave-org-{suffix}@example.test"),
        validation_status=ORGANIZER_APPROVED,
    )

    scanner_user = make_user(
        email=(f"leave-scanner-{suffix}@example.test"),
        role=roles["SCANNER"],
    )

    scanner_user.must_change_password = False
    scanner_user.phone = "+33612345678"
    scanner_user.save(
        update_fields=[
            "must_change_password",
            "phone",
            "updated_at",
        ],
    )

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_first_name="Scanner",
        invited_last_name="Test",
        invited_email=scanner_user.email,
        status=SCANNER_ACTIVE,
        activated_at=timezone.now(),
    )

    return (
        owner,
        organizer,
        scanner_user,
        scanner,
    )


def confirm_scanner_leave(
    *,
    scanner_user,
):
    client = APIClient()
    client.force_authenticate(
        user=scanner_user,
    )

    challenge_response = client.post(
        SECURITY_URL,
        {},
        format="json",
    )

    assert challenge_response.status_code == 200

    challenge_id = challenge_response.data["challenge_id"]

    code = derive_scanner_security_code(
        challenge_id,
    )

    response = client.post(
        REQUEST_URL,
        {
            "challenge_id": challenge_id,
            "code": code,
        },
        format="json",
    )

    return response


def leave_accept_otp_payload(
    *,
    owner,
    organizer,
    scanner,
):
    result = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=(SCANNER_SECURITY_ACTION_LEAVE_ACCEPT),
    )

    return {
        "challenge_id": str(
            result.challenge_id,
        ),
        "code": derive_scanner_security_code(
            result.challenge_id,
        ),
    }


@pytest.mark.django_db
def test_scanner_leave_security_code_does_not_create_request(
    roles,
):
    (
        _,
        _,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="otp-request-only",
    )

    client = APIClient()
    client.force_authenticate(
        user=scanner_user,
    )

    response = client.post(
        SECURITY_URL,
        {},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["expires_in_seconds"] == 300

    challenge = ScannerRevocationChallenge.objects.get(
        pk=response.data["challenge_id"],
    )

    assert challenge.action == (SCANNER_SECURITY_ACTION_LEAVE_REQUEST)
    assert challenge.requested_by_id == scanner_user.pk
    assert challenge.scanner_id == scanner.pk
    assert challenge.consumed_at is None

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE
    assert scanner.leave_requested_at is None


@pytest.mark.django_db
def test_scanner_can_request_leave_after_valid_otp(
    roles,
):
    (
        _,
        _,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="request",
    )

    response = confirm_scanner_leave(
        scanner_user=scanner_user,
    )

    assert response.status_code == 202
    assert response.data == {
        "status": SCANNER_LEAVE_REQUESTED,
    }

    scanner.refresh_from_db()

    assert scanner.status == (SCANNER_LEAVE_REQUESTED)
    assert scanner.leave_requested_at is not None


@pytest.mark.django_db
def test_direct_leave_request_without_otp_is_rejected(
    roles,
):
    (
        _,
        _,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="no-otp",
    )

    client = APIClient()
    client.force_authenticate(
        user=scanner_user,
    )

    response = client.post(
        REQUEST_URL,
        {},
        format="json",
    )

    assert response.status_code == 400

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE
    assert scanner.leave_requested_at is None


@pytest.mark.django_db
def test_invalid_scanner_leave_otp_does_not_create_request(
    roles,
):
    (
        _,
        _,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="bad-otp",
    )

    client = APIClient()
    client.force_authenticate(
        user=scanner_user,
    )

    challenge_response = client.post(
        SECURITY_URL,
        {},
        format="json",
    )

    assert challenge_response.status_code == 200

    challenge_id = challenge_response.data["challenge_id"]

    valid_code = derive_scanner_security_code(
        challenge_id,
    )

    wrong_code = "000000" if valid_code != "000000" else "999999"

    response = client.post(
        REQUEST_URL,
        {
            "challenge_id": challenge_id,
            "code": wrong_code,
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "OTP_INVALID"

    challenge = ScannerRevocationChallenge.objects.get(
        pk=challenge_id,
    )

    assert challenge.attempts == 1
    assert challenge.consumed_at is None

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE
    assert scanner.leave_requested_at is None


@pytest.mark.django_db
def test_scanner_leave_otp_email_goes_only_to_scanner(
    roles,
    monkeypatch,
):
    (
        owner,
        organizer,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="recipient",
    )

    sent = []

    class Sender:
        def send_email(
            self,
            **kwargs,
        ):
            sent.append(kwargs)

    monkeypatch.setattr(
        "apps.organizing." "scanner_security_tasks." "build_notification_sender",
        lambda: Sender(),
    )

    result = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=scanner_user.pk,
        action=(SCANNER_SECURITY_ACTION_LEAVE_REQUEST),
    )

    task_result = send_scanner_security_code_email.run(
        challenge_id=str(
            result.challenge_id,
        ),
    )

    assert task_result == {
        "sent": True,
    }

    assert len(sent) == 1
    assert sent[0]["to"] == scanner_user.email
    assert sent[0]["to"] != owner.email
    assert "demande scanner" in sent[0]["subject"].lower()


@pytest.mark.django_db
def test_duplicate_leave_request_is_rejected(
    roles,
):
    (
        _,
        _,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="duplicate",
    )

    scanner.status = SCANNER_LEAVE_REQUESTED
    scanner.leave_requested_at = timezone.now()
    scanner.version += 1
    scanner.save(
        update_fields=[
            "status",
            "leave_requested_at",
            "version",
            "updated_at",
        ],
    )

    client = APIClient()
    client.force_authenticate(
        user=scanner_user,
    )

    response = client.post(
        SECURITY_URL,
        {},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "SCANNER_LEAVE_ALREADY_REQUESTED"


@pytest.mark.django_db
def test_organizer_can_reject_scanner_leave_request(
    roles,
):
    (
        owner,
        _,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="reject",
    )

    requested = confirm_scanner_leave(
        scanner_user=scanner_user,
    )

    assert requested.status_code == 202

    scanner.refresh_from_db()

    organizer_client = APIClient()
    organizer_client.force_authenticate(
        user=owner,
    )

    response = organizer_client.post(
        (f"/api/v1/organizers/me/" f"scanners/{scanner.pk}/" f"leave-request"),
        {
            "decision": "REJECT",
        },
        format="json",
        HTTP_IF_MATCH=f'"{scanner.version}"',
    )

    assert response.status_code == 204

    scanner.refresh_from_db()

    assert scanner.status == SCANNER_ACTIVE
    assert scanner.leave_rejected_at is not None
    assert scanner.user.is_active is True


@pytest.mark.django_db
def test_organizer_can_accept_scanner_leave_request(
    roles,
):
    (
        owner,
        organizer,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="accept",
    )

    requested = confirm_scanner_leave(
        scanner_user=scanner_user,
    )

    assert requested.status_code == 202

    scanner.refresh_from_db()

    organizer_client = APIClient()
    organizer_client.force_authenticate(
        user=owner,
    )

    otp = leave_accept_otp_payload(
        owner=owner,
        organizer=organizer,
        scanner=scanner,
    )

    response = organizer_client.post(
        (f"/api/v1/organizers/me/" f"scanners/{scanner.pk}/" f"leave-request"),
        {
            "decision": "ACCEPT",
            **otp,
        },
        format="json",
        HTTP_IF_MATCH=f'"{scanner.version}"',
    )

    assert response.status_code == 204

    scanner.refresh_from_db()
    scanner.user.refresh_from_db()

    assert scanner.status == SCANNER_DELETED
    assert scanner.removed_at is not None
    assert scanner.removed_by_id == owner.pk
    assert scanner.user.is_active is False


@pytest.mark.django_db
def test_non_scanner_cannot_request_leave_otp(
    roles,
):
    (
        owner,
        _,
        _,
        _,
    ) = make_context(
        roles=roles,
        suffix="forbidden",
    )

    client = APIClient()
    client.force_authenticate(
        user=owner,
    )

    response = client.post(
        SECURITY_URL,
        {},
        format="json",
    )

    assert response.status_code == 403

    response = client.post(
        REQUEST_URL,
        {
            "challenge_id": ("00000000-0000-4000-" "8000-000000000001"),
            "code": "000000",
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_leave_accept_stale_version_does_not_consume_otp(
    roles,
):
    (
        owner,
        organizer,
        scanner_user,
        scanner,
    ) = make_context(
        roles=roles,
        suffix="stale-accept",
    )

    ScannerLeaveService.request(
        user_id=scanner_user.pk,
    )

    scanner.refresh_from_db()

    payload = leave_accept_otp_payload(
        owner=owner,
        organizer=organizer,
        scanner=scanner,
    )

    challenge = scanner.revocation_challenges.get(
        pk=payload["challenge_id"],
    )

    original_version = scanner.version

    client = APIClient()
    client.force_authenticate(
        user=owner,
    )

    stale_response = client.post(
        (f"/api/v1/organizers/me/" f"scanners/{scanner.pk}/" f"leave-request"),
        {
            "decision": "ACCEPT",
            **payload,
        },
        format="json",
        HTTP_IF_MATCH='"999"',
    )

    assert stale_response.status_code == 409
    assert stale_response.data["error"]["code"] == "STALE_RESOURCE"

    challenge.refresh_from_db()
    scanner.refresh_from_db()

    assert challenge.consumed_at is None
    assert scanner.version == original_version

    retry_response = client.post(
        (f"/api/v1/organizers/me/" f"scanners/{scanner.pk}/" f"leave-request"),
        {
            "decision": "ACCEPT",
            **payload,
        },
        format="json",
        HTTP_IF_MATCH=f'"{scanner.version}"',
    )

    assert retry_response.status_code == 204

    challenge.refresh_from_db()

    assert challenge.consumed_at is not None
