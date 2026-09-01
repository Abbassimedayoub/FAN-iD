from __future__ import annotations

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organizing.constants import ORGANIZER_APPROVED, SCANNER_ACTIVE
from apps.organizing.models import Organizer, Scanner, ScannerRevocationChallenge
from apps.organizing.scanner_security import (
    SCANNER_SECURITY_ACTION_REVOKE,
    SCANNER_SECURITY_OTP_MAX_ATTEMPTS,
    ScannerSecurityOtpInvalidError,
    ScannerSecurityOtpMaxAttemptsError,
    ScannerSecurityService,
    derive_scanner_security_code,
)

User = get_user_model()


@pytest.mark.django_db
def test_security_code_is_six_digits_and_not_stored_plaintext(
    roles,
    monkeypatch,
):
    monkeypatch.setattr(
        "apps.organizing.scanner_security_tasks." "send_scanner_security_code_email.delay",
        lambda **kwargs: None,
    )

    owner = User.objects.create_user(
        email="otp-owner@example.test",
        password="Strong-Organizer-2026!",
        first_name="Nadia",
        last_name="Owner",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="OTP Org",
        contact_email=owner.email,
        validation_status=ORGANIZER_APPROVED,
    )

    scanner_user = User.objects.create_user(
        email="otp-scanner@example.test",
        password="Strong-Scanner-2026!",
        first_name="Amine",
        last_name="Scanner",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
    )

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_first_name="Amine",
        invited_last_name="Scanner",
        invited_email=scanner_user.email,
        status=SCANNER_ACTIVE,
    )

    result = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    challenge = ScannerRevocationChallenge.objects.get(
        pk=result.challenge_id,
    )

    code = derive_scanner_security_code(
        challenge.pk,
    )

    assert len(code) == 6
    assert code.isdigit()
    assert challenge.code_hash != code
    assert len(challenge.code_hash) == 64
    assert result.expires_in_seconds == 300


@pytest.mark.django_db
def test_new_security_code_invalidates_previous(
    roles,
    monkeypatch,
):
    monkeypatch.setattr(
        "apps.organizing.scanner_security_tasks." "send_scanner_security_code_email.delay",
        lambda **kwargs: None,
    )

    owner = User.objects.create_user(
        email="otp-owner-rotate@example.test",
        password="Strong-Organizer-2026!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="OTP Rotate",
        contact_email=owner.email,
        validation_status=ORGANIZER_APPROVED,
    )

    scanner_user = User.objects.create_user(
        email="otp-scanner-rotate@example.test",
        password="Strong-Scanner-2026!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
    )

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_email=scanner_user.email,
        status=SCANNER_ACTIVE,
    )

    first = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    second = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    old = ScannerRevocationChallenge.objects.get(
        pk=first.challenge_id,
    )

    assert old.consumed_at is not None
    assert first.challenge_id != second.challenge_id


@pytest.mark.django_db
def test_security_code_is_single_use(
    roles,
    monkeypatch,
):
    monkeypatch.setattr(
        "apps.organizing.scanner_security_tasks." "send_scanner_security_code_email.delay",
        lambda **kwargs: None,
    )

    owner = User.objects.create_user(
        email="otp-owner-single@example.test",
        password="Strong-Organizer-2026!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="OTP Single",
        contact_email=owner.email,
        validation_status=ORGANIZER_APPROVED,
    )

    scanner_user = User.objects.create_user(
        email="otp-scanner-single@example.test",
        password="Strong-Scanner-2026!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
    )

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_email=scanner_user.email,
        status=SCANNER_ACTIVE,
    )

    result = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    code = derive_scanner_security_code(
        result.challenge_id,
    )

    ScannerSecurityService.consume(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        challenge_id=result.challenge_id,
        code=code,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    with pytest.raises(ScannerSecurityOtpInvalidError):
        ScannerSecurityService.consume(
            organizer=organizer,
            scanner_id=scanner.pk,
            requested_by_id=owner.pk,
            challenge_id=result.challenge_id,
            code=code,
            action=SCANNER_SECURITY_ACTION_REVOKE,
        )


@pytest.mark.django_db
def test_security_code_locks_after_five_bad_attempts(
    roles,
    monkeypatch,
):
    monkeypatch.setattr(
        "apps.organizing.scanner_security_tasks." "send_scanner_security_code_email.delay",
        lambda **kwargs: None,
    )

    owner = User.objects.create_user(
        email="otp-owner-attempts@example.test",
        password="Strong-Organizer-2026!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["ORGANIZER"],
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="OTP Attempts",
        contact_email=owner.email,
        validation_status=ORGANIZER_APPROVED,
    )

    scanner_user = User.objects.create_user(
        email="otp-scanner-attempts@example.test",
        password="Strong-Scanner-2026!",
        date_of_birth=datetime.date(1990, 1, 1),
        terms_accepted_at=timezone.now(),
        role=roles["SCANNER"],
    )

    scanner = Scanner.objects.create(
        organizer=organizer,
        user=scanner_user,
        invited_by=owner,
        invited_email=scanner_user.email,
        status=SCANNER_ACTIVE,
    )

    result = ScannerSecurityService.request(
        organizer=organizer,
        scanner_id=scanner.pk,
        requested_by_id=owner.pk,
        action=SCANNER_SECURITY_ACTION_REVOKE,
    )

    for _ in range(SCANNER_SECURITY_OTP_MAX_ATTEMPTS - 1):
        with pytest.raises(ScannerSecurityOtpInvalidError):
            ScannerSecurityService.consume(
                organizer=organizer,
                scanner_id=scanner.pk,
                requested_by_id=owner.pk,
                challenge_id=result.challenge_id,
                code="000000",
                action=SCANNER_SECURITY_ACTION_REVOKE,
            )

    with pytest.raises(ScannerSecurityOtpMaxAttemptsError):
        ScannerSecurityService.consume(
            organizer=organizer,
            scanner_id=scanner.pk,
            requested_by_id=owner.pk,
            challenge_id=result.challenge_id,
            code="000000",
            action=SCANNER_SECURITY_ACTION_REVOKE,
        )
