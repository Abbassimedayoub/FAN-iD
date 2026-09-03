from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)

from apps.organizing.constants import (
    ORGANIZER_APPROVED,
    ORGANIZER_COMMISSION_AGREED,
    ORGANIZER_COMMISSION_CANCELLED,
    ORGANIZER_COMMISSION_NEGOTIATING,
    ORGANIZER_REJECTED,
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
from apps.organizing.views import (
    AdminOrganizerCommissionAcceptView,
    AdminOrganizerCommissionNegotiationView,
    AdminOrganizerCommissionProposalView,
    OrganizerCommissionAcceptView,
    OrganizerCommissionNegotiationView,
    OrganizerCommissionProposalView,
)

User = get_user_model()

AUTH_LEVEL_PASSWORD = 1
AUTH_LEVEL_STEP_UP = 2


@pytest.fixture
def factory() -> APIRequestFactory:
    return APIRequestFactory()


def make_user(
    roles,
    *,
    email,
    role,
):
    return User.objects.create_user(
        email=email,
        password="Commission-API-Solide-2026!",
        first_name="Commission",
        last_name="API",
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
    suffix,
):
    owner = make_user(
        roles,
        email=(f"commission-api-owner-" f"{suffix}@example.test"),
        role="ORGANIZER",
    )

    admin = make_user(
        roles,
        email=(f"commission-api-admin-" f"{suffix}@example.test"),
        role="ADMIN",
    )

    organizer = Organizer.objects.create(
        user=owner,
        org_name=f"Commission API {suffix}",
        contact_email=(f"commission-{suffix}@example.test"),
    )

    OrganizerCommissionService.create_initial_proposal(
        organizer_id=organizer.pk,
        actor_id=owner.pk,
        rate=Decimal("0.1200"),
    )

    organizer.refresh_from_db()

    return owner, admin, organizer


def organizer_call(
    factory,
    *,
    view,
    user,
    method="get",
    data=None,
    if_match=None,
):
    headers = {}

    if if_match is not None:
        headers["HTTP_IF_MATCH"] = if_match

    if method == "get":
        request = factory.get(
            "/api/v1/organizers/me/" "commission-negotiation",
            **headers,
        )
    else:
        request = factory.post(
            "/api/v1/organizers/me/" "commission-action",
            data or {},
            format="json",
            **headers,
        )

    force_authenticate(
        request,
        user=user,
    )

    return view.as_view()(
        request,
    )


def admin_call(
    factory,
    *,
    view,
    user,
    organizer_id,
    method="post",
    data=None,
    if_match=None,
    auth_level=AUTH_LEVEL_STEP_UP,
):
    headers = {}

    if if_match is not None:
        headers["HTTP_IF_MATCH"] = if_match

    if method == "get":
        request = factory.get(
            (f"/api/v1/admin/organizers/" f"{organizer_id}/" "commission-negotiation"),
            **headers,
        )
    else:
        request = factory.post(
            (f"/api/v1/admin/organizers/" f"{organizer_id}/" "commission-action"),
            data or {},
            format="json",
            **headers,
        )

    force_authenticate(
        request,
        user=user,
    )

    setattr(
        request,
        "auth_level",
        auth_level,
    )

    return view.as_view()(
        request,
        organizer_id=organizer_id,
    )


@pytest.mark.django_db
def test_organizer_reads_initial_negotiation(
    factory,
    roles,
):
    owner, _, organizer = make_context(
        roles,
        "owner-read",
    )

    response = organizer_call(
        factory,
        view=OrganizerCommissionNegotiationView,
        user=owner,
    )

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"1"'
    assert response.data["organizer_id"] == str(organizer.pk)
    assert response.data["commission_status"] == (ORGANIZER_COMMISSION_NEGOTIATING)
    assert response.data["agreed_rate"] is None
    assert response.data["proposals"][0]["rate"] == ("0.1200")


@pytest.mark.django_db
def test_admin_reads_without_step_up(
    factory,
    roles,
):
    _, admin, organizer = make_context(
        roles,
        "admin-read",
    )

    response = admin_call(
        factory,
        view=AdminOrganizerCommissionNegotiationView,
        user=admin,
        organizer_id=organizer.pk,
        method="get",
        auth_level=AUTH_LEVEL_PASSWORD,
    )

    assert response.status_code == 200, response.data
    assert response.data["commission_status"] == (ORGANIZER_COMMISSION_NEGOTIATING)


@pytest.mark.django_db
def test_admin_counter_requires_step_up(
    factory,
    roles,
):
    _, admin, organizer = make_context(
        roles,
        "counter-step-up",
    )

    response = admin_call(
        factory,
        view=AdminOrganizerCommissionProposalView,
        user=admin,
        organizer_id=organizer.pk,
        data={
            "commission_rate": "0.0800",
        },
        if_match='"1"',
        auth_level=AUTH_LEVEL_PASSWORD,
    )

    assert response.status_code == 403, response.data
    assert response.data["error"]["code"] == ("STEP_UP_REQUIRED")

    assert (
        OrganizerCommissionProposal.objects.filter(
            organizer=organizer,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_alternating_counter_proposals_keep_history(
    factory,
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "history",
    )

    response = admin_call(
        factory,
        view=AdminOrganizerCommissionProposalView,
        user=admin,
        organizer_id=organizer.pk,
        data={
            "commission_rate": "0.0800",
        },
        if_match='"1"',
    )

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"2"'

    response = organizer_call(
        factory,
        view=OrganizerCommissionProposalView,
        user=owner,
        method="post",
        data={
            "commission_rate": "0.1000",
        },
        if_match='"2"',
    )

    assert response.status_code == 200, response.data
    assert response["ETag"] == '"3"'

    assert [item["proposer_role"] for item in response.data["proposals"]] == [
        "ORGANIZER",
        "ADMIN",
        "ORGANIZER",
    ]

    assert [item["rate"] for item in response.data["proposals"]] == [
        "0.1200",
        "0.0800",
        "0.1000",
    ]


@pytest.mark.django_db
def test_organizer_accept_auto_approves_pending_account(
    factory,
    roles,
):
    owner, admin, organizer = make_context(
        roles,
        "owner-auto-approve",
    )

    assert organizer.validation_status != ORGANIZER_APPROVED

    counter = admin_call(
        factory,
        view=AdminOrganizerCommissionProposalView,
        user=admin,
        organizer_id=organizer.pk,
        data={
            "commission_rate": "0.0800",
        },
        if_match=f'"{organizer.version}"',
    )

    assert counter.status_code == 200, counter.data

    response = organizer_call(
        factory,
        view=OrganizerCommissionAcceptView,
        user=owner,
        method="post",
        if_match=counter["ETag"],
    )

    assert response.status_code == 200, response.data
    assert response.data["validation_status"] == ORGANIZER_APPROVED
    assert response.data["commission_status"] == (
        ORGANIZER_COMMISSION_AGREED
    )
    assert response.data["agreed_rate"] == "0.0800"

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.commission_rate == Decimal("0.0800")
    assert organizer.commission_agreed_at is not None
    assert organizer.validated_at is not None
    assert organizer.validated_by_id == admin.pk


@pytest.mark.django_db
def test_admin_accept_requires_step_up(
    factory,
    roles,
):
    _, admin, organizer = make_context(
        roles,
        "admin-accept",
    )

    denied = admin_call(
        factory,
        view=AdminOrganizerCommissionAcceptView,
        user=admin,
        organizer_id=organizer.pk,
        if_match='"1"',
        auth_level=AUTH_LEVEL_PASSWORD,
    )

    assert denied.status_code == 403, denied.data
    assert denied.data["error"]["code"] == ("STEP_UP_REQUIRED")

    organizer.refresh_from_db()
    assert organizer.commission_agreed_at is None

    accepted = admin_call(
        factory,
        view=AdminOrganizerCommissionAcceptView,
        user=admin,
        organizer_id=organizer.pk,
        if_match='"1"',
    )

    assert accepted.status_code == 200, accepted.data
    assert accepted.data["validation_status"] == ORGANIZER_APPROVED
    assert accepted.data["commission_status"] == (
        ORGANIZER_COMMISSION_AGREED
    )
    assert accepted.data["agreed_rate"] == "0.1200"

    organizer.refresh_from_db()

    assert organizer.validation_status == ORGANIZER_APPROVED
    assert organizer.validated_at is not None
    assert organizer.validated_by_id == admin.pk


@pytest.mark.django_db
def test_rejected_account_exposes_cancelled_negotiation(
    factory,
    roles,
):
    owner, _, organizer = make_context(
        roles,
        "cancelled",
    )

    Organizer.objects.filter(
        pk=organizer.pk,
    ).update(
        validation_status=ORGANIZER_REJECTED,
    )

    response = organizer_call(
        factory,
        view=OrganizerCommissionNegotiationView,
        user=owner,
    )

    assert response.status_code == 200, response.data
    assert response.data["commission_status"] == (ORGANIZER_COMMISSION_CANCELLED)


@pytest.mark.django_db
def test_six_routes_are_mounted(
    roles,
):
    _, _, organizer = make_context(
        roles,
        "routes",
    )

    checks = [
        (
            "/api/v1/organizers/me/" "commission-negotiation",
            OrganizerCommissionNegotiationView,
        ),
        (
            "/api/v1/organizers/me/" "commission-proposals",
            OrganizerCommissionProposalView,
        ),
        (
            "/api/v1/organizers/me/" "commission-accept",
            OrganizerCommissionAcceptView,
        ),
        (
            (f"/api/v1/admin/organizers/" f"{organizer.pk}/" "commission-negotiation"),
            AdminOrganizerCommissionNegotiationView,
        ),
        (
            (f"/api/v1/admin/organizers/" f"{organizer.pk}/" "commission-proposals"),
            AdminOrganizerCommissionProposalView,
        ),
        (
            (f"/api/v1/admin/organizers/" f"{organizer.pk}/" "commission-accept"),
            AdminOrganizerCommissionAcceptView,
        ),
    ]

    for url, expected_view in checks:
        match = resolve(url)
        assert match.func.view_class is expected_view
