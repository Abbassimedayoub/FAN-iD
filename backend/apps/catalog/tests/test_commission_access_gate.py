from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Category, Event
from apps.catalog.permissions import (
    IsCommissionAgreedOrganizer,
)
from apps.catalog.views import (
    EventArchiveView,
    EventCancelView,
    EventDetailView,
    EventImageView,
    EventListCreateView,
    EventPostponeView,
    EventPublishView,
    EventScannerAssignmentCollectionView,
    EventScannerAssignmentDetailView,
    EventSuspendView,
    EventUnarchiveView,
    TicketCategoryDetailView,
    TicketCategoryListCreateView,
)
from apps.organizing.constants import (
    ORGANIZER_APPROVED,
)
from apps.organizing.models import Organizer
from apps.organizing.services.commissions import (
    OrganizerCommissionService,
)
from apps.organizing.services.onboarding import (
    OrganizerOnboardingService,
)

User = get_user_model()

EVENTS_URL = "/api/v1/events"


def make_user(
    roles,
    *,
    email,
    role,
):
    return User.objects.create_user(
        email=email,
        password="Commission-Gate-Solide-2026!",
        first_name="Commission",
        last_name="Gate",
        date_of_birth=datetime.date(
            1990,
            1,
            1,
        ),
        terms_accepted_at=timezone.now(),
        role=roles[role],
    )


def event_payload(
    category,
):
    starts_at = timezone.now() + datetime.timedelta(days=5)

    return {
        "category_id": str(category.pk),
        "name": "Evenement commission",
        "description": "Verrou commercial",
        "starts_at": starts_at.isoformat(),
        "ends_at": (starts_at + datetime.timedelta(hours=2)).isoformat(),
    }


def test_all_event_management_views_require_commission():
    views = [
        EventImageView,
        EventListCreateView,
        EventDetailView,
        EventPublishView,
        EventPostponeView,
        EventSuspendView,
        EventCancelView,
        EventArchiveView,
        EventUnarchiveView,
        TicketCategoryListCreateView,
        TicketCategoryDetailView,
        EventScannerAssignmentCollectionView,
        EventScannerAssignmentDetailView,
    ]

    for view in views:
        assert IsCommissionAgreedOrganizer in view.permission_classes, view.__name__


@pytest.mark.django_db
def test_approved_without_commission_is_blocked(
    roles,
):
    owner = make_user(
        roles,
        email="commission-gate-owner@example.test",
        role="ORGANIZER",
    )

    admin = make_user(
        roles,
        email="commission-gate-admin@example.test",
        role="ADMIN",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="Commission Gate",
        contact_email="gate@example.test",
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

    assert organizer.validation_status == (ORGANIZER_APPROVED)
    assert organizer.commission_agreed_at is None

    category = Category.objects.create(
        name="Commission Gate Category",
    )

    client = APIClient()
    client.force_authenticate(
        user=owner,
    )

    response = client.post(
        EVENTS_URL,
        event_payload(category),
        format="json",
    )

    assert response.status_code == 403, response.data
    assert response.data["error"]["code"] == ("COMMISSION_NOT_AGREED")
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_agreement_unlocks_event_creation(
    roles,
):
    owner = make_user(
        roles,
        email="commission-unlock-owner@example.test",
        role="ORGANIZER",
    )

    admin = make_user(
        roles,
        email="commission-unlock-admin@example.test",
        role="ADMIN",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="Commission Unlock",
        contact_email="unlock@example.test",
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

    category = Category.objects.create(
        name="Commission Unlock Category",
    )

    client = APIClient()
    client.force_authenticate(
        user=owner,
    )

    response = client.post(
        EVENTS_URL,
        event_payload(category),
        format="json",
    )

    assert response.status_code == 201, response.data
    assert Event.objects.count() == 1


@pytest.mark.django_db
def test_pending_keeps_not_approved_error(
    roles,
):
    owner = make_user(
        roles,
        email="commission-pending-owner@example.test",
        role="ORGANIZER",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name="Commission Pending",
        contact_email="pending@example.test",
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.1200"),
    )

    category = Category.objects.create(
        name="Commission Pending Category",
    )

    client = APIClient()
    client.force_authenticate(
        user=owner,
    )

    response = client.post(
        EVENTS_URL,
        event_payload(category),
        format="json",
    )

    assert response.status_code == 403, response.data
    assert response.data["error"]["code"] == ("ORGANIZER_NOT_APPROVED")
    assert Event.objects.count() == 0
