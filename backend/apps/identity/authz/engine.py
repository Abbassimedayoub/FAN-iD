"""
The decision engine: the system's single authorization entry point.

No other part of the code should compare a role to a string, check
`user.is_staff`, or implement ownership checks ad hoc. A stray
`if role == "ADMIN"` in a view is invisible to the policy, so it will not be
reviewed, tested, or removed when it becomes obsolete. Outside this package,
code should call `authorize()`.

The engine is a PURE function: same inputs, same verdict, with no database,
clock, or randomness. That makes an exhaustive role/action matrix fast enough
to run on every test execution.
"""

from __future__ import annotations

from ..constants import AUTH_LEVEL_STEP_UP, ROLE_ORGANIZER
from .actions import Action
from .decisions import ALLOW, Decision, Reason, deny
from .rules import POLICY, Grant, Scope
from .subject import Resource, Subject


def authorize(subject: Subject, action: Action, resource: Resource | None = None) -> Decision:
    """
    Answer whether this subject may perform this action on this resource.

    The ORDER of checks is a security decision:

    1. authentication, 2. account state, 3. known role, 4. known action,
    5. role grant (RBAC), 6. resource ownership/scope (ABAC),
    7. authentication level.

    Ownership is checked BEFORE step-up authentication. In the opposite order,
    a non-owner could receive `STEP_UP_REQUIRED`, revealing information about
    what would be allowed on a resource they should not know exists.
    """
    if not subject.is_authenticated:
        return deny(Reason.UNAUTHENTICATED)

    # A disabled or anonymized account loses ALL rights, including access to its
    # own data. Anonymization means there is no longer an active subject entitled
    # to read those data.
    if not subject.is_active:
        return deny(Reason.INACTIVE_SUBJECT)

    grants = POLICY.get(subject.role or "")
    if grants is None:
        return deny(Reason.UNKNOWN_ROLE)

    # `action` is typed as `Action`, but an untyped caller may still pass an
    # arbitrary string. The explicit check prevents a typo from looking like a
    # legitimate `ROLE_NOT_GRANTED` policy denial.
    if not isinstance(action, Action):
        return deny(Reason.UNKNOWN_ACTION)

    grant = grants.get(action)
    if grant is None:
        return deny(Reason.ROLE_NOT_GRANTED)

    scope_decision = _check_scope(subject, grant, resource)
    if not scope_decision.allowed:
        return scope_decision

    if grant.step_up and subject.auth_level < AUTH_LEVEL_STEP_UP:
        return deny(Reason.STEP_UP_REQUIRED)

    return ALLOW


def require_approved_organizer(subject: Subject) -> Decision:
    """
    Check the actor-level `ORGANIZER_APPROVED` prerequisite.

    This rule is not resource-specific and does not replace RBAC/ABAC. A future
    business write must compose its action permission with
    `IsApprovedOrganizer`.

    The state is already attached to the request by the owning `organizing`
    context, so this engine remains pure and never touches the database.
    """
    if not subject.is_authenticated:
        return deny(Reason.UNAUTHENTICATED)

    if not subject.is_active:
        return deny(Reason.INACTIVE_SUBJECT)

    if (subject.role or "") not in POLICY:
        return deny(Reason.UNKNOWN_ROLE)

    if subject.role != ROLE_ORGANIZER:
        return deny(Reason.ROLE_NOT_GRANTED)

    if not subject.organizer_is_approved:
        return deny(Reason.ORGANIZER_NOT_APPROVED)

    return ALLOW


def _check_scope(subject: Subject, grant: Grant, resource: Resource | None) -> Decision:
    """ABAC layer: does the role grant apply to THIS resource instance?"""
    if grant.scope is Scope.NONE or grant.scope is Scope.ANY:
        # No instance-level ownership check is required. A supplied resource is
        # ignored, so it cannot broaden the grant.
        return ALLOW

    if resource is None:
        # The grant is instance-scoped but no instance was supplied. Deny rather
        # than interpreting missing data as absence of restriction.
        return deny(Reason.RESOURCE_ATTRIBUTE_MISSING)

    if grant.scope is Scope.SELF:
        if resource.owner_id is None:
            return deny(Reason.RESOURCE_ATTRIBUTE_MISSING)
        return ALLOW if resource.owner_id == subject.user_id else deny(Reason.NOT_OWNER)

    if grant.scope is Scope.OWN_ORGANIZER:
        if resource.organizer_id is None or subject.organizer_id is None:
            return deny(Reason.RESOURCE_ATTRIBUTE_MISSING)
        return ALLOW if resource.organizer_id == subject.organizer_id else deny(Reason.NOT_OWNER)

    # A new Scope value without handling here must fail closed.
    return deny(Reason.ROLE_NOT_GRANTED)


def may_attempt(subject: Subject, action: Action) -> Decision:
    """
    Pre-check WITHOUT resource-ownership verification.

    Used by DRF `has_permission`, which runs before the view loads an object.
    It answers whether the role may ever perform the action and whether the
    subject has the required authentication level.

    Step-up authentication IS checked here, unlike ownership. The required auth
    level is a policy property, not a resource property, so checking it reveals
    nothing about a specific resource.

    IMPORTANT: an allowed result here authorizes NOTHING on a particular
    instance. It must always be followed by either `authorize()` with a
    resource through `has_object_permission`, or SQL filtering scoped to the
    subject for collection endpoints.
    """
    if not subject.is_authenticated:
        return deny(Reason.UNAUTHENTICATED)
    if not subject.is_active:
        return deny(Reason.INACTIVE_SUBJECT)

    grants = POLICY.get(subject.role or "")
    if grants is None:
        return deny(Reason.UNKNOWN_ROLE)
    if not isinstance(action, Action):
        return deny(Reason.UNKNOWN_ACTION)

    grant = grants.get(action)
    if grant is None:
        return deny(Reason.ROLE_NOT_GRANTED)
    if grant.step_up and subject.auth_level < AUTH_LEVEL_STEP_UP:
        return deny(Reason.STEP_UP_REQUIRED)
    return ALLOW
