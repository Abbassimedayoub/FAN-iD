from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.exceptions import ConflictError
from apps.organizing.api import (
    resolve_organizer_commercial_context,
)
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_PENDING,
)
from apps.organizing.models import (
    Organizer,
    OrganizerCommissionProposal,
)
from apps.organizing.services.commissions import (
    OrganizerCommissionService,
)
from apps.organizing.services.onboarding import (
    OrganizerOnboardingService,
)

User = get_user_model()


def make_user(
    roles,
    *,
    email: str,
    role: str,
):
    return User.objects.create_user(
        email=email,
        password="Strong-Commission-2026!",
        first_name="Commission",
        last_name="Test",
        date_of_birth=datetime.date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles[role],
    )


def make_context(
    roles,
    suffix: str,
):
    owner = make_user(
        roles,
        email=f"commission-owner-{suffix}@example.test",
        role="ORGANIZER",
    )

    admin = make_user(
        roles,
        email=f"commission-admin-{suffix}@example.test",
        role="ADMIN",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name=f"Commission Arena {suffix}",
        contact_email=f"contact-{suffix}@example.test",
    )

    return owner, admin, organizer


@pytest.mark.django_db
def test_initial_proposal_does_not_open_account(
    roles,
):
    owner, _, organizer = make_context(
        roles,
        "initial",
    )

    proposal = (
        OrganizerCommissionService.create_initial_proposal(
            organizer_id=organizer.pk,
            actor_id=owner.pk,
            rate=Decimal("0.1200"),
        )
    )

    organizer.refresh_from_db()

    assert proposal.sequence == 1
    assert proposal.proposer_role == "ORGANIZER"
    assert proposal.rate == Decimal("0.1200")

    assert organizer.validation_status == ORGANIZER_PENDING
    assert organizer.commission_agreed_at is None
    assert organizer.commission_rate == Decimal("0.0000")


@pytest.mark.django_db
def test_admin_can_open_account_without_accepting_commission(
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "open-only",
    )

    proposal = (
        OrganizerCommissionService.create_initial_proposal(
            organizer_id=organizer.pk,
            actor_id=owner.pk,
            rate=Decimal("0.1200"),
        )
    )

    organizer = OrganizerOnboardingService.approve(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    proposal.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.commission_agreed_at is None
    assert organizer.commission_rate == Decimal("0.0000")
    assert proposal.accepted_at is None
    assert proposal.accepted_by_id is None

    context = resolve_organizer_commercial_context(
        user_id=owner.pk,
    )

    assert context == (
        organizer.pk,
        True,
        False,
    )


@pytest.mark.django_db
def test_negotiation_continues_after_account_is_open(
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "open-counter",
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.1200"),
    )

    organizer = OrganizerOnboardingService.approve(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    organizer = OrganizerCommissionService.admin_counter(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
        rate=Decimal("0.0800"),
    )

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.commission_agreed_at is None

    proposals = list(
        OrganizerCommissionProposal.objects.filter(
            organizer=organizer,
        )
    )

    assert [
        item.proposer_role
        for item in proposals
    ] == [
        "ORGANIZER",
        "ADMIN",
    ]


@pytest.mark.django_db
def test_organizer_accepting_admin_counter_auto_approves_account(
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "owner-auto-approve",
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.1200"),
    )

    organizer = OrganizerCommissionService.admin_counter(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
        rate=Decimal("0.0800"),
    )

    assert organizer.validation_status == ORGANIZER_PENDING

    organizer = OrganizerCommissionService.organizer_accept(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        expected_version=organizer.version,
    )

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.commission_rate == Decimal("0.0800")
    assert organizer.commission_agreed_at is not None
    assert organizer.validated_at is not None
    assert organizer.validated_by_id == admin.pk

    context = resolve_organizer_commercial_context(
        user_id=owner.pk,
    )

    assert context == (
        organizer.pk,
        True,
        True,
    )


@pytest.mark.django_db
def test_admin_accepting_commission_auto_approves_account(
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "agreement-auto-approve",
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.0900"),
    )

    assert organizer.validation_status == ORGANIZER_PENDING

    organizer = OrganizerCommissionService.admin_accept(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.commission_rate == Decimal("0.0900")
    assert organizer.commission_agreed_at is not None
    assert organizer.validated_at is not None
    assert organizer.validated_by_id == admin.pk

    context = resolve_organizer_commercial_context(
        user_id=owner.pk,
    )

    assert context == (
        organizer.pk,
        True,
        True,
    )


@pytest.mark.django_db
def test_multiple_counters_keep_complete_history_after_opening(
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "history",
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.1500"),
    )

    organizer = OrganizerOnboardingService.approve(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    organizer = OrganizerCommissionService.admin_counter(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
        rate=Decimal("0.0800"),
    )

    organizer = OrganizerCommissionService.organizer_counter(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        expected_version=organizer.version,
        rate=Decimal("0.1000"),
    )

    organizer = OrganizerCommissionService.admin_accept(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.commission_rate == Decimal("0.1000")
    assert organizer.commission_agreed_at is not None

    proposals = list(
        OrganizerCommissionProposal.objects.filter(
            organizer=organizer,
        )
    )

    assert [
        item.sequence
        for item in proposals
    ] == [
        1,
        2,
        3,
    ]

    assert [
        item.proposer_role
        for item in proposals
    ] == [
        "ORGANIZER",
        "ADMIN",
        "ORGANIZER",
    ]

    assert proposals[0].accepted_at is None
    assert proposals[1].accepted_at is None
    assert proposals[2].accepted_by_id == admin.pk


@pytest.mark.django_db
def test_negotiation_stops_after_financial_agreement(
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "final",
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.1000"),
    )

    organizer = OrganizerOnboardingService.approve(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    organizer = OrganizerCommissionService.admin_accept(
        organizer_id=organizer.pk,
        actor_id=admin.pk,
        expected_version=organizer.version,
    )

    with pytest.raises(ConflictError) as exc_info:
        OrganizerCommissionService.admin_counter(
            organizer_id=organizer.pk,
            actor_id=admin.pk,
            expected_version=organizer.version,
            rate=Decimal("0.0700"),
        )

    assert exc_info.value.code == "COMMISSION_ALREADY_AGREED"
