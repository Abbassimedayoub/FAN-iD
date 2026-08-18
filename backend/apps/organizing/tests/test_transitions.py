"""
Machine a etats de l onboarding organisateur.

Les 4 etats x 3 actions forment 12 cellules :
3 transitions autorisees et 9 transitions interdites.
"""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.exceptions import InvalidStateTransitionError, ValidationBusinessError
from apps.core.outbox.models import OutboxEvent
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_PENDING,
    ORGANIZER_REJECTED,
    ORGANIZER_SUSPENDED,
)
from apps.organizing.events import ORGANIZER_APPROVED_EVENT, ORGANIZER_REJECTED_EVENT
from apps.organizing.models import Organizer
from apps.organizing.services import OrganizerOnboardingService

User = get_user_model()

pytestmark = pytest.mark.django_db


def make_user(roles, email: str, role: str) -> Any:
    return User.objects.create_user(
        email=email,
        password="Chataigne-Orageuse-2026",
        first_name="Ines",
        last_name="Bouzid",
        date_of_birth=datetime.date(1990, 3, 12),
        terms_accepted_at=timezone.now(),
        role=roles[role],
    )


@pytest.fixture
def admin_user(db, roles):
    return make_user(roles, "admin-organizing@example.test", "ADMIN")


@pytest.fixture
def applicant(db, roles):
    return make_user(roles, "candidate-organizing@example.test", "ORGANIZER")


def make_organizer(applicant, *, status: str) -> Organizer:
    return Organizer.objects.create(
        user=applicant,
        org_name=f"Organisation {status}",
        contact_email="contact@example.test",
        validation_status=status,
    )


def test_pending_can_be_approved(applicant, admin_user):
    organizer = make_organizer(applicant, status=ORGANIZER_PENDING)

    result = OrganizerOnboardingService.approve(
        organizer_id=organizer.pk,
        actor_id=admin_user.pk,
        expected_version=organizer.version,
    )

    assert result.validation_status == ORGANIZER_APPROVED
    assert result.version == 2
    assert result.validated_by_id == admin_user.pk
    assert result.validated_at is not None
    assert result.rejection_reason is None

    event = OutboxEvent.objects.get()
    assert event.event_type == ORGANIZER_APPROVED_EVENT
    assert event.aggregate_id == organizer.pk
    assert event.actor_id == admin_user.pk
    assert event.payload == {"status": ORGANIZER_APPROVED}


def test_pending_can_be_rejected(applicant, admin_user):
    organizer = make_organizer(applicant, status=ORGANIZER_PENDING)

    result = OrganizerOnboardingService.reject(
        organizer_id=organizer.pk,
        actor_id=admin_user.pk,
        expected_version=organizer.version,
        reason="Dossier incomplet",
    )

    assert result.validation_status == ORGANIZER_REJECTED
    assert result.version == 2
    assert result.rejection_reason == "Dossier incomplet"
    assert result.validated_by_id == admin_user.pk
    assert result.validated_at is not None

    event = OutboxEvent.objects.get()
    assert event.event_type == ORGANIZER_REJECTED_EVENT
    assert event.payload == {"status": ORGANIZER_REJECTED}


def test_approved_can_be_suspended_without_outbox_event(applicant, admin_user):
    organizer = make_organizer(applicant, status=ORGANIZER_APPROVED)

    result = OrganizerOnboardingService.suspend(
        organizer_id=organizer.pk,
        actor_id=admin_user.pk,
        expected_version=organizer.version,
    )

    assert result.validation_status == ORGANIZER_SUSPENDED
    assert result.version == 2
    assert OutboxEvent.objects.count() == 0


@pytest.mark.parametrize(
    ("initial_state", "action"),
    [
        (ORGANIZER_PENDING, "suspend"),
        (ORGANIZER_APPROVED, "approve"),
        (ORGANIZER_APPROVED, "reject"),
        (ORGANIZER_REJECTED, "approve"),
        (ORGANIZER_REJECTED, "reject"),
        (ORGANIZER_REJECTED, "suspend"),
        (ORGANIZER_SUSPENDED, "approve"),
        (ORGANIZER_SUSPENDED, "reject"),
        (ORGANIZER_SUSPENDED, "suspend"),
    ],
)
def test_every_forbidden_transition_is_fail_closed(
    applicant,
    admin_user,
    initial_state,
    action,
):
    organizer = make_organizer(applicant, status=initial_state)
    original_version = organizer.version

    kwargs = {
        "organizer_id": organizer.pk,
        "actor_id": admin_user.pk,
        "expected_version": original_version,
    }

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        if action == "approve":
            OrganizerOnboardingService.approve(**kwargs)
        elif action == "reject":
            OrganizerOnboardingService.reject(reason="Refus", **kwargs)
        else:
            OrganizerOnboardingService.suspend(**kwargs)

    assert exc_info.value.code == "INVALID_STATE_TRANSITION"

    organizer.refresh_from_db()
    assert organizer.validation_status == initial_state
    assert organizer.version == original_version
    assert OutboxEvent.objects.count() == 0


def test_reject_requires_a_non_blank_reason(applicant, admin_user):
    organizer = make_organizer(applicant, status=ORGANIZER_PENDING)

    with pytest.raises(ValidationBusinessError):
        OrganizerOnboardingService.reject(
            organizer_id=organizer.pk,
            actor_id=admin_user.pk,
            expected_version=organizer.version,
            reason="   ",
        )

    organizer.refresh_from_db()
    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.version == 1
    assert OutboxEvent.objects.count() == 0
