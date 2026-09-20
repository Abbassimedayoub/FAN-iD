"""
Tests for the organizing-to-identity public boundary and fail-closed behavior.

The critical case proves that omitting request enrichment causes authorization
to deny rather than silently opening access. The module depends on identity only
through its public API boundary.
"""

from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from apps.identity.api import Action, IsApprovedOrganizer, grant_organizer_role
from apps.organizing.constants import ORGANIZER_APPROVED, ORGANIZER_PENDING
from apps.organizing.models import Organizer
from apps.organizing.permissions import OrganizerRecordPermission
from apps.organizing.views import OrganizerScopedMixin

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_user(roles, email: str, role: str = "ORGANIZER") -> Any:
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
def organizer_user(db, roles) -> Any:
    return make_user(roles, "organisateur@example.test")


@pytest.fixture
def dossier(organizer_user) -> Organizer:
    return Organizer.objects.create(
        user=organizer_user, org_name="Stade de France", contact_email="contact@example.test"
    )


def request_for(user, organizer_id=None):
    """Minimal request double containing only attributes read by permission adapters."""
    payload = SimpleNamespace(user=user)
    if organizer_id is not None:
        payload.organizer_id = organizer_id
    return payload


VIEW = SimpleNamespace(required_action=Action.ORGANIZER_READ, action=None, policy_actions={})


# ===========================================================================
# Fail-closed guarantee
# ===========================================================================


def test_forgetting_the_mixin_refuses_instead_of_allowing(dossier, organizer_user):
    """
    Without OrganizerScopedMixin, organizer_id is absent and owner-scoped authorization must fail
    closed.
    """
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(request_for(organizer_user), VIEW, dossier)

    assert granted is False


def test_the_enriched_request_authorizes_the_owner(dossier, organizer_user):
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(
        request_for(organizer_user, organizer_id=dossier.pk), VIEW, dossier
    )

    assert granted is True


def test_another_organizer_dossier_is_refused(dossier, organizer_user):
    """The action is granted in principle, but the resource belongs to another organizer."""
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(
        request_for(organizer_user, organizer_id=uuid.uuid4()), VIEW, dossier
    )

    assert granted is False


def test_the_resource_carries_the_state_for_the_next_lot(dossier, organizer_user):
    """Resource.state is populated for state-aware extensions without changing the engine signature."""
    resource = OrganizerRecordPermission().get_resource(request_for(organizer_user), VIEW, dossier)

    assert resource.organizer_id == dossier.pk
    assert resource.state == ORGANIZER_PENDING


# ===========================================================================
# The mixin
# ===========================================================================


def test_the_mixin_resolves_the_dossier_of_the_caller(dossier, organizer_user):
    resolved = OrganizerScopedMixin.resolve_organizer_id(request_for(organizer_user))

    assert resolved == dossier.pk


def test_the_mixin_resolves_pending_as_not_approved(dossier, organizer_user):
    organizer_id, approved = OrganizerScopedMixin.resolve_organizer_context(request_for(organizer_user))

    assert organizer_id == dossier.pk
    assert approved is False


def test_the_mixin_resolves_approved_as_approved(dossier, organizer_user):
    Organizer.objects.filter(pk=dossier.pk).update(validation_status=ORGANIZER_APPROVED)

    organizer_id, approved = OrganizerScopedMixin.resolve_organizer_context(request_for(organizer_user))

    assert organizer_id == dossier.pk
    assert approved is True


def test_the_mixin_resolves_context_in_one_query(
    dossier,
    organizer_user,
    django_assert_num_queries,
):
    with django_assert_num_queries(1):
        organizer_id, approved = OrganizerScopedMixin.resolve_organizer_context(request_for(organizer_user))

    assert organizer_id == dossier.pk
    assert approved is False


def test_the_mixin_resolves_nothing_for_an_account_without_dossier(organizer_user):
    organizer_id, approved = OrganizerScopedMixin.resolve_organizer_context(request_for(organizer_user))

    assert organizer_id is None
    assert approved is False


def test_the_mixin_resolves_nothing_for_an_anonymous_caller():
    anonymous = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

    organizer_id, approved = OrganizerScopedMixin.resolve_organizer_context(anonymous)

    assert organizer_id is None
    assert approved is False


# ===========================================================================
# Organizer-approval prerequisite for future write endpoints
# ===========================================================================


class _ApprovedOrganizerWriteView(OrganizerScopedMixin, APIView):
    """Test-only endpoint used to exercise future organizer-write authorization behavior."""

    permission_classes = [IsApprovedOrganizer]

    def post(self, request):
        return Response({"ok": True})


def _call_approved_organizer_write(user):
    request = APIRequestFactory().post(
        "/fake-organizer-write",
        {},
        format="json",
    )
    force_authenticate(request, user=user)
    return _ApprovedOrganizerWriteView.as_view()(request)


def test_pending_organizer_gets_organizer_not_approved(dossier, organizer_user):
    response = _call_approved_organizer_write(organizer_user)

    assert response.status_code == 403
    assert response.data["error"]["code"] == "ORGANIZER_NOT_APPROVED"


def test_approved_organizer_reaches_the_same_fake_write(dossier, organizer_user):
    Organizer.objects.filter(pk=dossier.pk).update(validation_status=ORGANIZER_APPROVED)

    response = _call_approved_organizer_write(organizer_user)

    assert response.status_code == 200
    assert response.data == {"ok": True}


# ===========================================================================
# L operation publique d `identity`
# ===========================================================================


def test_granting_the_role_takes_effect_in_the_database(roles, db):
    """
    No session revocation is required because the server reads the current user role on every
    authenticated request.
    """
    fan = make_user(roles, "supporter@example.test", role="FAN")

    assert grant_organizer_role(user_id=fan.pk) is True

    fan.refresh_from_db()
    assert fan.role.name == "ORGANIZER"


def test_granting_the_role_to_an_unknown_account_changes_nothing(db):
    assert grant_organizer_role(user_id=uuid.uuid4()) is False
