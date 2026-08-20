"""
La frontiere `organizing -> identity.api`, et la garantie fail-closed.

Le test qui porte le lot est
`test_forgetting_the_mixin_refuses_instead_of_allowing`. Sans lui, l option B
d ADR-S1-05 ne serait qu une convention : rien ne prouverait qu un oubli
d enrichissement REFUSE au lieu d ouvrir.

Ce fichier appartient a `apps.organizing`. Il ne peut donc importer d
`identity` que `identity.api` — et `import-linter` le verifie. Toute tentative
d y importer `identity.authz` ou `identity.permissions` casserait la CI, ce qui
est exactement l intention.
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
    """Requete minimale : les classes de permission ne lisent que ces attributs."""
    payload = SimpleNamespace(user=user)
    if organizer_id is not None:
        payload.organizer_id = organizer_id
    return payload


VIEW = SimpleNamespace(required_action=Action.ORGANIZER_READ, action=None, policy_actions={})


# ===========================================================================
# La garantie fail-closed
# ===========================================================================


def test_forgetting_the_mixin_refuses_instead_of_allowing(dossier, organizer_user):
    """
    **Le test qui porte le lot.**

    Sans `OrganizerScopedMixin`, la requete ne porte pas `organizer_id`. Le
    sujet se construit avec `organizer_id=None`, et `engine._check_scope`
    refuse avec `RESOURCE_ATTRIBUTE_MISSING`.

    C est ce qui distingue l option B d une convention : l oubli ne produit pas
    un acces ouvert par omission, il produit un refus rendu par le moteur.
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
    """Le droit existe, la ressource n est pas la sienne."""
    permission = OrganizerRecordPermission()

    granted = permission.has_object_permission(
        request_for(organizer_user, organizer_id=uuid.uuid4()), VIEW, dossier
    )

    assert granted is False


def test_the_resource_carries_the_state_for_the_next_lot(dossier, organizer_user):
    """
    `Resource.state` est renseigne des maintenant. Aucune portee ne le lit au
    Sprint 1 ; il existe pour que S1-A.8b branche les transitions sans toucher
    a la signature du moteur.
    """
    resource = OrganizerRecordPermission().get_resource(request_for(organizer_user), VIEW, dossier)

    assert resource.organizer_id == dossier.pk
    assert resource.state == ORGANIZER_PENDING


# ===========================================================================
# Le mixin
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
# Pre-requis d approbation sur une future ecriture organisateur
# ===========================================================================


class _ApprovedOrganizerWriteView(OrganizerScopedMixin, APIView):
    """Faux endpoint S2 : aucune route de production n est ajoutee au Sprint 1."""

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
    Aucune session n est revoquee : le serveur relit `user.role_id` a chaque
    requete depuis S1-A.6a, donc le changement vaut immediatement.
    """
    fan = make_user(roles, "supporter@example.test", role="FAN")

    assert grant_organizer_role(user_id=fan.pk) is True

    fan.refresh_from_db()
    assert fan.role.name == "ORGANIZER"


def test_granting_the_role_to_an_unknown_account_changes_nothing(db):
    assert grant_organizer_role(user_id=uuid.uuid4()) is False
