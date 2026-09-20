"""
DRF authorization adapters: request-to-decision translation only.

The pure policy matrix is tested separately. These tests cover action
resolution, resource mapping, HTTP denial translation, and the absence of SQL
queries on the authorization path.
"""

from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.identity.authz import Action
from apps.identity.authz.context import ROLE_NAMES_BY_ID, UNKNOWN_ROLE, subject_from_request
from apps.identity.constants import AUTH_LEVEL_PASSWORD, AUTH_LEVEL_STEP_UP, ROLE_IDS
from apps.identity.permissions import (
    ActionPermission,
    BasePolicyPermission,
    IsApprovedOrganizer,
    MethodScopedActionPermission,
    OrganizerResourcePermission,
    SelfResourcePermission,
)

factory = APIRequestFactory()

USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
ORG_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")


def fake_user(role: str = "FAN", *, is_active: bool = True, anonymized: bool = False) -> SimpleNamespace:
    """
    Minimal user double containing only attributes read by subject_from_request; these tests
    exercise translation rather than model persistence.
    """
    return SimpleNamespace(
        pk=USER_ID,
        is_authenticated=True,
        is_active=is_active,
        role_id=ROLE_IDS[role],
        anonymized_at=datetime.datetime(2026, 1, 1) if anonymized else None,
    )


def make_request(user: object | None, *, method: str = "get", auth_level: int | None = None):
    request = getattr(factory, method)("/whatever")
    request.user = user if user is not None else SimpleNamespace(is_authenticated=False)
    if auth_level is not None:
        request.auth_level = auth_level
    return request


class _View(APIView):
    """Bare view whose required_action is read by the permission adapter."""

    required_action = Action.DEVICE_LIST_SELF


class _RevokeView(APIView):
    required_action = Action.DEVICE_REVOKE_SELF


class _MisconfiguredView(APIView):
    """No declared action: deliberate configuration error."""


# ===========================================================================
# Resolution de l action
# ===========================================================================


def test_a_view_without_a_declared_action_is_refused_not_allowed():
    """Missing authorization configuration must fail closed rather than imply permission."""
    permission = BasePolicyPermission()
    assert permission.has_permission(make_request(fake_user()), _MisconfiguredView()) is False
    assert permission.code == "FORBIDDEN"


def test_action_permission_resolves_the_action_from_the_viewset_table():
    view = SimpleNamespace(action="list", policy_actions={"list": Action.SESSION_LIST_SELF})
    permission = ActionPermission()
    assert permission.get_action(make_request(fake_user()), view) is Action.SESSION_LIST_SELF


def test_a_viewset_method_absent_from_the_table_is_refused():
    """Adding a method without assigning an action makes it inaccessible."""
    view = SimpleNamespace(action="export", policy_actions={"list": Action.SESSION_LIST_SELF})
    permission = ActionPermission()
    assert permission.get_action(make_request(fake_user()), view) is None
    assert permission.has_permission(make_request(fake_user()), view) is False


def test_method_scoped_permission_splits_read_from_write():
    view = SimpleNamespace(
        read_action=Action.USER_READ_SELF,
        write_action=Action.USER_UPDATE_SELF,
        action=None,
        policy_actions={},
    )
    permission = MethodScopedActionPermission()
    assert permission.get_action(make_request(fake_user()), view) is Action.USER_READ_SELF
    assert permission.get_action(make_request(fake_user(), method="patch"), view) is Action.USER_UPDATE_SELF


# ===========================================================================
# The verdict comes from the policy engine
# ===========================================================================


def test_an_anonymous_request_is_refused():
    assert BasePolicyPermission().has_permission(make_request(None), _View()) is False


def test_a_role_that_never_holds_the_action_is_refused_at_the_preflight():
    view = SimpleNamespace(required_action=Action.ORGANIZER_APPROVE, action=None, policy_actions={})
    fan = make_request(fake_user("FAN"), auth_level=AUTH_LEVEL_STEP_UP)
    admin = make_request(fake_user("ADMIN"), auth_level=AUTH_LEVEL_STEP_UP)
    assert ActionPermission().has_permission(fan, view) is False
    assert ActionPermission().has_permission(admin, view) is True

    # Even for an administrator, the pre-check enforces step-up before any object is loaded.
    weak = make_request(fake_user("ADMIN"), auth_level=AUTH_LEVEL_PASSWORD)
    permission = ActionPermission()
    assert permission.has_permission(weak, view) is False
    assert permission.code == "STEP_UP_REQUIRED"


def test_the_preflight_passes_but_the_object_check_refuses_someone_else_s_device():
    permission = SelfResourcePermission()
    request = make_request(fake_user("FAN"))
    view = _View()
    assert permission.has_permission(request, view) is True

    mine = SimpleNamespace(user_id=USER_ID)
    theirs = SimpleNamespace(user_id=OTHER_USER_ID)
    assert permission.has_object_permission(request, view, mine) is True
    assert permission.has_object_permission(request, view, theirs) is False


def test_the_refusal_never_tells_the_client_whose_resource_it_was():
    """Detailed NOT_OWNER reasoning stays in logs while the client receives the opaque FORBIDDEN response."""
    permission = SelfResourcePermission()
    request = make_request(fake_user("FAN"))
    permission.has_object_permission(request, _View(), SimpleNamespace(user_id=OTHER_USER_ID))
    assert permission.code == "FORBIDDEN"


def test_the_base_class_refuses_a_self_scoped_action_because_it_designates_no_resource():
    """The base adapter cannot grant access by omission."""
    permission = BasePolicyPermission()
    granted = permission.has_object_permission(
        make_request(fake_user("FAN")), _View(), SimpleNamespace(user_id=USER_ID)
    )
    assert granted is False


def test_the_owner_lookup_can_target_the_user_object_itself():
    class _OnSelf(SelfResourcePermission):
        owner_lookup = "pk"

    user = fake_user("FAN")
    assert _OnSelf().has_object_permission(make_request(user), _View(), user) is True


def test_an_organizer_scoped_resource_is_refused_while_no_organizer_is_resolved():
    """
    A request with no organizer context must fail closed with missing-resource context rather than
    gaining owner scope.
    """
    view = SimpleNamespace(required_action=Action.TICKET_SCAN, action=None, policy_actions={})
    permission = OrganizerResourcePermission()
    request = make_request(fake_user("SCANNER"))
    assert permission.has_permission(request, view) is True
    assert permission.has_object_permission(request, view, SimpleNamespace(organizer_id=ORG_ID)) is False


# ===========================================================================
# Approbation organisateur
# ===========================================================================


def test_organizer_approval_permission_is_fail_closed_and_specialized():
    request = make_request(fake_user("ORGANIZER"))

    permission = IsApprovedOrganizer()
    assert permission.has_permission(request, _View()) is False
    assert permission.code == "ORGANIZER_NOT_APPROVED"

    request.organizer_approved = True
    assert IsApprovedOrganizer().has_permission(request, _View()) is True


def test_organizer_approval_permission_does_not_replace_rbac():
    request = make_request(fake_user("FAN"))
    request.organizer_approved = True

    permission = IsApprovedOrganizer()

    assert permission.has_permission(request, _View()) is False
    assert permission.code == "FORBIDDEN"


# ===========================================================================
# Verification renforcee
# ===========================================================================


def test_revoking_a_device_requires_step_up_and_says_so_to_the_client():
    permission = SelfResourcePermission()
    mine = SimpleNamespace(user_id=USER_ID)

    weak = make_request(fake_user("FAN"), auth_level=AUTH_LEVEL_PASSWORD)
    assert permission.has_object_permission(weak, _RevokeView(), mine) is False
    assert permission.code == "STEP_UP_REQUIRED"

    strong = make_request(fake_user("FAN"), auth_level=AUTH_LEVEL_STEP_UP)
    assert permission.has_object_permission(strong, _RevokeView(), mine) is True


def test_a_request_without_any_declared_auth_level_falls_back_to_the_lowest():
    """Incomplete context denies step-up actions rather than granting them."""
    subject = subject_from_request(make_request(fake_user("FAN")))
    assert subject.auth_level == AUTH_LEVEL_PASSWORD


# ===========================================================================
# Traduction du sujet
# ===========================================================================


def test_an_anonymized_account_keeps_no_right_at_all():
    subject = subject_from_request(make_request(fake_user("ADMIN", anonymized=True)))
    assert subject.is_active is False


def test_an_unrecognised_role_id_yields_a_sentinel_role_not_an_anonymous_subject():
    """Unknown-role context and anonymous context both deny, but diagnostics must distinguish them."""
    user = fake_user()
    user.role_id = uuid.uuid4()
    subject = subject_from_request(make_request(user))
    assert subject.role == UNKNOWN_ROLE
    assert subject.is_authenticated is True


def test_every_seeded_role_id_resolves_to_its_name():
    assert set(ROLE_NAMES_BY_ID.values()) == set(ROLE_IDS)


# ===========================================================================
# Cout du controle
# ===========================================================================


@pytest.mark.django_db
def test_authorizing_a_real_user_costs_zero_query(django_assert_num_queries, roles):
    """
    Authorization checks must never trigger database queries; role resolution uses already-loaded
    fixed identifiers.
    """
    from apps.identity.models import User

    user = User.objects.create_user(
        email="authz@example.test",
        password="Motdepasse-2026",
        date_of_birth=datetime.date(1990, 1, 1),
        role=roles["FAN"],
        terms_accepted_at=timezone.now(),
    )
    request = make_request(user)

    with django_assert_num_queries(0):
        subject = subject_from_request(request)
        assert SelfResourcePermission().has_permission(request, _View()) is True

    assert subject.role == "FAN"
    assert subject.user_id == user.pk


class _ApproveView(APIView):
    """Real view used only for the end-to-end adapter test below."""

    required_action = Action.ORGANIZER_APPROVE
    permission_classes = [ActionPermission]

    def get(self, request):
        return Response({"ok": True})


@pytest.mark.django_db
def test_the_drf_cycle_really_calls_the_policy_and_turns_a_refusal_into_403(roles):
    """
    End-to-end coverage verifies both allowed and denied paths, using force_authenticate so DRF sees
    the intended subject.
    """
    from rest_framework.test import force_authenticate

    from apps.identity.models import User

    def call(user, auth_level):
        # Reuse make_request so auth_level is installed on the raw request.
        # avant que DRF ne l enveloppe. Ni mise en sourdine de mypy ni
        # Use direct assignment rather than suppressing type issues or using unnecessary setattr.
        # directe ne fasse deja.
        request = make_request(user, auth_level=auth_level)
        force_authenticate(request, user=user)
        return _ApproveView.as_view()(request)

    fan = User.objects.create_user(
        email="fan-403@example.test",
        password="Motdepasse-2026",
        date_of_birth=datetime.date(1990, 1, 1),
        role=roles["FAN"],
        terms_accepted_at=timezone.now(),
    )
    admin = User.objects.create_user(
        email="admin-200@example.test",
        password="Motdepasse-2026",
        date_of_birth=datetime.date(1990, 1, 1),
        role=roles["ADMIN"],
        terms_accepted_at=timezone.now(),
    )

    assert call(fan, AUTH_LEVEL_STEP_UP).status_code == 403
    # Droits suffisants mais authentification simple : refus, motif different.
    assert call(admin, AUTH_LEVEL_PASSWORD).status_code == 403
    assert call(admin, AUTH_LEVEL_STEP_UP).status_code == 200
