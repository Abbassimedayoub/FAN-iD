"""
Authorization matrix: four roles by every declared action, covering both grants
and denials.

Expected policy cells are written independently from the implementation so a
policy change must be reflected explicitly in the tests rather than deriving
expected values from the code under test. The verbosity is intentional: the
matrix should remain auditable without executing the policy engine.
"""

from __future__ import annotations

import uuid

import pytest

from apps.identity.authz import (
    POLICY,
    Action,
    Reason,
    Resource,
    Scope,
    Subject,
    authorize,
    may_attempt,
    require_approved_organizer,
)
from apps.identity.authz.decisions import ALLOW, Decision, deny
from apps.identity.constants import (
    AUTH_LEVEL_PASSWORD,
    AUTH_LEVEL_STEP_UP,
    ROLE_ADMIN,
    ROLE_FAN,
    ROLE_ORGANIZER,
    ROLE_SCANNER,
)

ROLES = (ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER, ROLE_ADMIN)

#: `None` means denied; `(scope, step_up)` describes an explicit grant.
EXPECTED: dict[tuple[str, Action], tuple[Scope, bool] | None] = {
    # ----------------------------------------------------------------- FAN
    (ROLE_FAN, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_FAN, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_FAN, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    (ROLE_FAN, Action.ORGANIZER_CREATE): (Scope.NONE, False),
    (ROLE_FAN, Action.ORGANIZER_READ): None,
    (ROLE_FAN, Action.ORGANIZER_UPDATE): None,
    (ROLE_FAN, Action.ORGANIZER_APPROVE): None,
    (ROLE_FAN, Action.ORGANIZER_REJECT): None,
    (ROLE_FAN, Action.ORGANIZER_SUSPEND): None,
    (ROLE_FAN, Action.SCANNER_INVITE): None,
    (ROLE_FAN, Action.SCANNER_READ): None,
    (ROLE_FAN, Action.SCANNER_REVOKE): None,
    (ROLE_FAN, Action.SCANNER_CREDENTIAL_RESET): None,
    (ROLE_FAN, Action.TICKET_SCAN): None,
    (ROLE_FAN, Action.CATEGORY_READ): None,
    (ROLE_FAN, Action.CATEGORY_CREATE): None,
    (ROLE_FAN, Action.CATEGORY_DELETE): None,
    (ROLE_FAN, Action.EVENT_CREATE): None,
    (ROLE_FAN, Action.EVENT_READ): None,
    (ROLE_FAN, Action.EVENT_UPDATE): None,
    (ROLE_FAN, Action.EVENT_DELETE): None,
    (ROLE_FAN, Action.EVENT_PUBLISH): None,
    (ROLE_FAN, Action.EVENT_ARCHIVE): None,
    (ROLE_FAN, Action.EVENT_UNARCHIVE): None,
    (ROLE_FAN, Action.EVENT_POSTPONE): None,
    (ROLE_FAN, Action.EVENT_SUSPEND): None,
    (ROLE_FAN, Action.EVENT_CANCEL): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_CREATE): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_READ): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_UPDATE): None,
    (ROLE_FAN, Action.TICKET_CATEGORY_DELETE): None,
    # ----------------------------------------------------------- ORGANIZER
    (ROLE_ORGANIZER, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_ORGANIZER, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_ORGANIZER, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_ORGANIZER, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    # One account may have only one organizer.
    (ROLE_ORGANIZER, Action.ORGANIZER_CREATE): None,
    (ROLE_ORGANIZER, Action.ORGANIZER_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.ORGANIZER_UPDATE): (Scope.OWN_ORGANIZER, False),
    # An organizer does not moderate its own dossier.
    (ROLE_ORGANIZER, Action.ORGANIZER_APPROVE): None,
    (ROLE_ORGANIZER, Action.ORGANIZER_REJECT): None,
    (ROLE_ORGANIZER, Action.ORGANIZER_SUSPEND): None,
    (ROLE_ORGANIZER, Action.SCANNER_INVITE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.SCANNER_READ): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.SCANNER_REVOKE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.SCANNER_CREDENTIAL_RESET): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.TICKET_SCAN): None,
    (ROLE_ORGANIZER, Action.CATEGORY_READ): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.CATEGORY_CREATE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.CATEGORY_DELETE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_CREATE): (Scope.NONE, False),
    (ROLE_ORGANIZER, Action.EVENT_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_UPDATE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_DELETE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_PUBLISH): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_ARCHIVE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_UNARCHIVE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_POSTPONE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_SUSPEND): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.EVENT_CANCEL): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_CREATE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_UPDATE): (Scope.OWN_ORGANIZER, False),
    (ROLE_ORGANIZER, Action.TICKET_CATEGORY_DELETE): (Scope.OWN_ORGANIZER, False),
    # ------------------------------------------------------------- SCANNER
    (ROLE_SCANNER, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_SCANNER, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_SCANNER, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    (ROLE_SCANNER, Action.ORGANIZER_CREATE): None,
    (ROLE_SCANNER, Action.ORGANIZER_READ): (Scope.OWN_ORGANIZER, False),
    (ROLE_SCANNER, Action.ORGANIZER_UPDATE): None,
    (ROLE_SCANNER, Action.ORGANIZER_APPROVE): None,
    (ROLE_SCANNER, Action.ORGANIZER_REJECT): None,
    (ROLE_SCANNER, Action.ORGANIZER_SUSPEND): None,
    (ROLE_SCANNER, Action.SCANNER_INVITE): None,
    (ROLE_SCANNER, Action.SCANNER_READ): None,
    (ROLE_SCANNER, Action.SCANNER_REVOKE): None,
    (ROLE_SCANNER, Action.SCANNER_CREDENTIAL_RESET): None,
    (ROLE_SCANNER, Action.TICKET_SCAN): (Scope.OWN_ORGANIZER, False),
    (ROLE_SCANNER, Action.CATEGORY_READ): None,
    (ROLE_SCANNER, Action.CATEGORY_CREATE): None,
    (ROLE_SCANNER, Action.CATEGORY_DELETE): None,
    (ROLE_SCANNER, Action.EVENT_CREATE): None,
    (ROLE_SCANNER, Action.EVENT_READ): None,
    (ROLE_SCANNER, Action.EVENT_UPDATE): None,
    (ROLE_SCANNER, Action.EVENT_DELETE): None,
    (ROLE_SCANNER, Action.EVENT_PUBLISH): None,
    (ROLE_SCANNER, Action.EVENT_ARCHIVE): None,
    (ROLE_SCANNER, Action.EVENT_UNARCHIVE): None,
    (ROLE_SCANNER, Action.EVENT_POSTPONE): None,
    (ROLE_SCANNER, Action.EVENT_SUSPEND): None,
    (ROLE_SCANNER, Action.EVENT_CANCEL): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_CREATE): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_READ): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_UPDATE): None,
    (ROLE_SCANNER, Action.TICKET_CATEGORY_DELETE): None,
    # --------------------------------------------------------------- ADMIN
    (ROLE_ADMIN, Action.USER_READ_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.USER_UPDATE_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.USER_DELETE_SELF): (Scope.SELF, True),
    (ROLE_ADMIN, Action.DEVICE_LIST_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.DEVICE_REVOKE_SELF): (Scope.SELF, True),
    (ROLE_ADMIN, Action.SESSION_LIST_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.SESSION_REVOKE_SELF): (Scope.SELF, False),
    (ROLE_ADMIN, Action.ORGANIZER_CREATE): None,
    (ROLE_ADMIN, Action.ORGANIZER_READ): (Scope.ANY, False),
    (ROLE_ADMIN, Action.ORGANIZER_UPDATE): (Scope.ANY, False),
    (ROLE_ADMIN, Action.ORGANIZER_APPROVE): (Scope.ANY, True),
    (ROLE_ADMIN, Action.ORGANIZER_REJECT): (Scope.ANY, True),
    (ROLE_ADMIN, Action.ORGANIZER_SUSPEND): (Scope.ANY, True),
    (ROLE_ADMIN, Action.SCANNER_INVITE): None,
    (ROLE_ADMIN, Action.SCANNER_READ): None,
    (ROLE_ADMIN, Action.SCANNER_REVOKE): None,
    (ROLE_ADMIN, Action.SCANNER_CREDENTIAL_RESET): None,
    # Separation of duties: administration is not ticket scanning.
    (ROLE_ADMIN, Action.TICKET_SCAN): None,
    (ROLE_ADMIN, Action.CATEGORY_READ): None,
    (ROLE_ADMIN, Action.CATEGORY_CREATE): None,
    (ROLE_ADMIN, Action.CATEGORY_DELETE): None,
    (ROLE_ADMIN, Action.EVENT_CREATE): None,
    (ROLE_ADMIN, Action.EVENT_READ): None,
    (ROLE_ADMIN, Action.EVENT_UPDATE): None,
    (ROLE_ADMIN, Action.EVENT_DELETE): None,
    (ROLE_ADMIN, Action.EVENT_PUBLISH): None,
    (ROLE_ADMIN, Action.EVENT_ARCHIVE): None,
    (ROLE_ADMIN, Action.EVENT_UNARCHIVE): None,
    (ROLE_ADMIN, Action.EVENT_POSTPONE): None,
    (ROLE_ADMIN, Action.EVENT_SUSPEND): None,
    (ROLE_ADMIN, Action.EVENT_CANCEL): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_CREATE): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_READ): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_UPDATE): None,
    (ROLE_ADMIN, Action.TICKET_CATEGORY_DELETE): None,
}

ALL_CELLS = [(role, action) for role in ROLES for action in Action]


# ===========================================================================
# 1. The matrix covers the whole action catalog
# ===========================================================================


def test_the_expected_matrix_covers_every_role_and_every_action():
    """
    Adding an action or role without an explicit policy decision must fail here.
    This keeps the matrix exhaustive rather than silently omitting new cells.
    """
    assert set(EXPECTED) == set(ALL_CELLS)
    assert len(ALL_CELLS) == 140, "4 roles x 35 actions"


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_policy_matches_the_declared_matrix(role: str, action: Action):
    """Every policy cell must match the independently declared matrix above."""
    grant = POLICY[role].get(action)
    expected = EXPECTED[(role, action)]

    if expected is None:
        assert grant is None, f"{role} ne devrait PAS avoir {action}"
        return

    scope, step_up = expected
    assert grant is not None, f"{role} devrait avoir {action}"
    assert grant.scope is scope
    assert grant.step_up is step_up


# ===========================================================================
# 2. The engine applies both grants and denials from the matrix
# ===========================================================================

USER_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
ORG_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
OTHER_ORG_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")


def _subject(role: str, *, step_up: bool = True) -> Subject:
    """Nominal subject: active, owner-scoped, and step-up verified."""
    return Subject(
        user_id=USER_ID,
        role=role,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP if step_up else AUTH_LEVEL_PASSWORD,
        organizer_id=ORG_ID,
    )


#: Resource satisfying every owner-scoped grant.
OWNED = Resource(owner_id=USER_ID, organizer_id=ORG_ID)
#: Resource owned by someone else on both ownership axes.
FOREIGN = Resource(owner_id=OTHER_USER_ID, organizer_id=OTHER_ORG_ID)


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_engine_grants_exactly_what_the_matrix_declares(role: str, action: Action):
    """With an owned resource, only explicitly granted matrix cells may pass."""
    decision = authorize(_subject(role), action, OWNED)
    assert decision.allowed is (EXPECTED[(role, action)] is not None), decision.reason


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_engine_refuses_every_action_on_a_resource_owned_by_someone_else(role: str, action: Action):
    """
    Denial half of the matrix on a foreign resource.

    Only grants with NONE or ANY scope may remain allowed; every owner-scoped
    grant must fail its ABAC ownership check.
    """
    decision = authorize(_subject(role), action, FOREIGN)
    expected = EXPECTED[(role, action)]
    should_pass = expected is not None and expected[0] in (Scope.NONE, Scope.ANY)
    assert decision.allowed is should_pass, decision.reason


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_step_up_actions_are_refused_to_a_password_only_session(role: str, action: Action):
    """Step-up protected actions must fail for password-only sessions."""
    decision = authorize(_subject(role, step_up=False), action, OWNED)
    expected = EXPECTED[(role, action)]
    should_pass = expected is not None and not expected[1]
    assert decision.allowed is should_pass, decision.reason
    if expected is not None and expected[1]:
        assert decision.reason is Reason.STEP_UP_REQUIRED


# ===========================================================================
# 3. Structural denials
# ===========================================================================


@pytest.mark.parametrize("action", list(Action))
def test_an_anonymous_subject_is_refused_everything(action: Action):
    from apps.identity.authz import ANONYMOUS

    decision = authorize(ANONYMOUS, action, OWNED)
    assert decision.allowed is False
    assert decision.reason is Reason.UNAUTHENTICATED


@pytest.mark.parametrize("action", list(Action))
def test_a_deactivated_subject_loses_every_right_including_over_itself(action: Action):
    """An inactive or anonymized account retains no rights, including self-service access."""
    subject = Subject(user_id=USER_ID, role=ROLE_ADMIN, is_active=False, auth_level=AUTH_LEVEL_STEP_UP)
    decision = authorize(subject, action, OWNED)
    assert decision.allowed is False
    assert decision.reason is Reason.INACTIVE_SUBJECT


def test_an_unknown_role_obtains_nothing():
    """A role unknown to the code policy inherits no permissions."""
    subject = Subject(user_id=USER_ID, role="SUPERUSER", is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    decision = authorize(subject, Action.USER_READ_SELF, OWNED)
    assert decision.allowed is False
    assert decision.reason is Reason.UNKNOWN_ROLE


def test_an_action_outside_the_catalogue_is_refused_and_named_as_such():
    """An arbitrary action string must be distinguished from a legitimate policy denial."""
    decision = authorize(_subject(ROLE_ADMIN), "identity:user:read_slef", OWNED)  # type: ignore[arg-type]
    assert decision.allowed is False
    assert decision.reason is Reason.UNKNOWN_ACTION


def test_a_scoped_action_without_any_resource_is_refused():
    """Instance-scoped grants fail closed when no resource instance is supplied."""
    decision = authorize(_subject(ROLE_FAN), Action.USER_READ_SELF, None)
    assert decision.allowed is False
    assert decision.reason is Reason.RESOURCE_ATTRIBUTE_MISSING


def test_a_resource_missing_the_attribute_the_rule_needs_is_refused():
    decision = authorize(_subject(ROLE_ORGANIZER), Action.ORGANIZER_READ, Resource(owner_id=USER_ID))
    assert decision.allowed is False
    assert decision.reason is Reason.RESOURCE_ATTRIBUTE_MISSING


def test_a_subject_without_organizer_cannot_reach_an_organizer_scoped_resource():
    """A scanner detached from every organizer cannot scan tickets."""
    subject = Subject(user_id=USER_ID, role=ROLE_SCANNER, is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    decision = authorize(subject, Action.TICKET_SCAN, Resource(organizer_id=ORG_ID))
    assert decision.allowed is False
    assert decision.reason is Reason.RESOURCE_ATTRIBUTE_MISSING


# ===========================================================================
# 4. Check ordering must not disclose resource information
# ===========================================================================


def test_ownership_is_checked_before_step_up_so_that_a_stranger_learns_nothing():
    """
    A non-owner receives NOT_OWNER before any step-up hint, so authorization does
    not reveal information about resources the subject cannot access.
    """
    subject = Subject(user_id=USER_ID, role=ROLE_FAN, is_active=True, auth_level=AUTH_LEVEL_PASSWORD)
    decision = authorize(subject, Action.DEVICE_REVOKE_SELF, Resource(owner_id=OTHER_USER_ID))
    assert decision.allowed is False
    assert decision.reason is Reason.NOT_OWNER


def test_an_inactive_subject_is_named_inactive_before_any_role_check():
    """An inactive subject remains inactive before any unknown-role check."""
    subject = Subject(user_id=USER_ID, role="SUPERUSER", is_active=False)
    assert authorize(subject, Action.USER_READ_SELF, OWNED).reason is Reason.INACTIVE_SUBJECT


# ===========================================================================
# 5. Structural properties of the policy
# ===========================================================================


def test_the_policy_table_cannot_be_modified_at_runtime():
    """The runtime policy must be immutable so tests and concurrent workers cannot mutate shared grants."""
    with pytest.raises(TypeError):
        POLICY[ROLE_FAN][Action.ORGANIZER_APPROVE] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        POLICY["ROOT"] = {}  # type: ignore[index]


def test_only_the_admin_role_holds_an_unscoped_grant():
    """ANY scope bypasses ownership checks and must remain an explicit, visible exception."""
    unscoped = {
        (role, action)
        for role, grants in POLICY.items()
        for action, grant in grants.items()
        if grant.scope is Scope.ANY
    }
    assert {role for role, _ in unscoped} == {ROLE_ADMIN}


def test_every_irreversible_action_requires_step_up():
    """Sensitive irreversible actions must retain their step-up requirement across all roles."""
    irreversible = {Action.USER_DELETE_SELF, Action.DEVICE_REVOKE_SELF, Action.ORGANIZER_APPROVE}
    for role, grants in POLICY.items():
        for action in irreversible & set(grants):
            assert grants[action].step_up is True, f"{role} / {action} sans verification renforcee"


# ===========================================================================
# 6. Organizer approval prerequisite
# ===========================================================================


def test_pending_organizer_is_refused_by_the_approval_gate():
    subject = Subject(
        user_id=USER_ID,
        role=ROLE_ORGANIZER,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP,
        organizer_id=ORG_ID,
        organizer_is_approved=False,
    )

    decision = require_approved_organizer(subject)

    assert decision.allowed is False
    assert decision.reason is Reason.ORGANIZER_NOT_APPROVED


def test_approved_organizer_passes_the_approval_gate():
    subject = Subject(
        user_id=USER_ID,
        role=ROLE_ORGANIZER,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP,
        organizer_id=ORG_ID,
        organizer_is_approved=True,
    )

    assert require_approved_organizer(subject) is ALLOW


def test_non_organizer_cannot_pass_the_gate_even_with_a_true_primitive():
    subject = Subject(
        user_id=USER_ID,
        role=ROLE_FAN,
        is_active=True,
        auth_level=AUTH_LEVEL_STEP_UP,
        organizer_is_approved=True,
    )

    decision = require_approved_organizer(subject)

    assert decision.allowed is False
    assert decision.reason is Reason.ROLE_NOT_GRANTED


# ===========================================================================
# 7. RBAC pre-check and verdict guardrails
# ===========================================================================


def test_may_attempt_ignores_ownership_and_must_never_be_used_alone():
    """may_attempt intentionally ignores ownership because DRF calls it before the object is loaded."""
    subject = Subject(user_id=USER_ID, role=ROLE_FAN, is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    assert may_attempt(subject, Action.USER_READ_SELF).allowed is True
    assert authorize(subject, Action.USER_READ_SELF, FOREIGN).allowed is False


@pytest.mark.parametrize(("role", "action"), ALL_CELLS)
def test_may_attempt_enforces_step_up_even_without_any_resource(role: str, action: Action):
    """Step-up must still be enforced by the pre-check for actions that load no object instance."""
    expected = EXPECTED[(role, action)]
    decision = may_attempt(_subject(role, step_up=False), action)
    assert decision.allowed is (expected is not None and not expected[1]), decision.reason
    if expected is not None and expected[1]:
        assert decision.reason is Reason.STEP_UP_REQUIRED


def test_may_attempt_still_refuses_an_action_the_role_never_holds():
    subject = Subject(user_id=USER_ID, role=ROLE_FAN, is_active=True, auth_level=AUTH_LEVEL_STEP_UP)
    decision = may_attempt(subject, Action.ORGANIZER_APPROVE)
    assert decision.allowed is False
    assert decision.reason is Reason.ROLE_NOT_GRANTED


def test_a_decision_cannot_be_evaluated_as_a_boolean():
    """`if decision:` is forbidden because an explicit `decision.allowed` check is required."""
    with pytest.raises(TypeError, match="decision.allowed"):
        bool(ALLOW)


def test_a_decision_cannot_be_built_with_an_incoherent_reason():
    with pytest.raises(ValueError):
        Decision(allowed=True, reason=Reason.NOT_OWNER)
    with pytest.raises(ValueError):
        Decision(allowed=False, reason=Reason.ALLOWED)
    with pytest.raises(ValueError):
        deny(Reason.ALLOWED)


def test_the_subject_is_immutable():
    """Prevent privilege escalation through mutation after a decision is created."""
    subject = _subject(ROLE_FAN)
    with pytest.raises(AttributeError):
        subject.role = ROLE_ADMIN  # type: ignore[misc]
