"""
DRF adapters. They adapt requests to the authorization engine; they do not make
authorization decisions themselves.

Each class resolves the requested action and target resource, then delegates the
verdict to the policy engine. No adapter compares roles or checks `is_staff`,
so the policy table remains the single authorization source of truth.

The classes differ only in how actions and resources are resolved. `DenyAll`,
the framework-level default refusal, lives in `apps.core.permissions` because
it is a safety guard rather than a domain rule.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, ClassVar

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.observability.metrics import AUTHZ_ROLE_ANONYMOUS, fanid_authz_denied_total

from .authz import Action, Decision, Reason, Resource, authorize, may_attempt, require_approved_organizer
from .authz.context import subject_from_request

logger = logging.getLogger(__name__)

#: Opaque message returned for denials that offer no client-side corrective action.
#: Detailed internal reasons stay in correlated logs rather than revealing
#: resource existence or ownership information.
FORBIDDEN_MESSAGE = "Vous n avez pas la permission d effectuer cette action."
FORBIDDEN_CODE = "FORBIDDEN"

#: Step-up is intentionally actionable: the client must know that stronger
#: verification is required. This does not reveal resource existence because
#: ownership has already been checked before this reason can be returned.
STEP_UP_MESSAGE = "Une verification d identite renforcee est requise pour cette action."
STEP_UP_CODE = "STEP_UP_REQUIRED"

ORGANIZER_NOT_APPROVED_MESSAGE = "Votre organisation doit etre approuvee pour effectuer cette action."
ORGANIZER_NOT_APPROVED_CODE = "ORGANIZER_NOT_APPROVED"


def _client_error_for(reason: Reason) -> tuple[str, str]:
    """Translate only denial reasons that the client can act on."""
    if reason is Reason.STEP_UP_REQUIRED:
        return STEP_UP_MESSAGE, STEP_UP_CODE

    if reason is Reason.ORGANIZER_NOT_APPROVED:
        return ORGANIZER_NOT_APPROVED_MESSAGE, ORGANIZER_NOT_APPROVED_CODE

    return FORBIDDEN_MESSAGE, FORBIDDEN_CODE


class IsApprovedOrganizer(BasePermission):
    """
    Actor-level prerequisite for organizer writes.

    This permission composes with `ActionPermission`; it does not replace it.
    The policy engine decides, while this adapter only builds the subject and
    maps a denial into DRF's permission interface.
    """

    message: str = FORBIDDEN_MESSAGE
    code: str = FORBIDDEN_CODE

    def has_permission(self, request: Any, view: Any) -> bool:
        subject = subject_from_request(request)
        decision = require_approved_organizer(subject)

        if decision.allowed:
            return True

        self.message, self.code = _client_error_for(decision.reason)

        logger.warning(
            "authorization.organizer_approval_denied",
            extra={
                "authz_reason": decision.reason.value,
                "authz_role": (subject.role if subject.role is not None else AUTHZ_ROLE_ANONYMOUS),
            },
        )
        return False


class BasePolicyPermission(BasePermission):
    """
    Shared base: resolve the action, delegate the decision, and map denials.

    No resource is associated by default. Resource-scoped actions therefore fail
    closed unless a subclass explicitly knows how to identify the target.
    """

    #: Action declared by a view when it exposes a single policy action.
    required_action: ClassVar[Action | None] = None

    #: Read by DRF when constructing a 403 response. Declared here explicitly
    #: because BasePermission does not define these attributes.
    message: str = FORBIDDEN_MESSAGE
    code: str = FORBIDDEN_CODE

    def get_action(self, request: Any, view: Any) -> Action | None:
        action = getattr(view, "required_action", None) or self.required_action
        return action if isinstance(action, Action) else None

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource()

    # -- DRF entry points ----------------------------------------------------

    def has_permission(self, request: Any, view: Any) -> bool:
        """
        Pre-check called before an object is loaded.

        It can validate role/action eligibility but not object ownership. Detail
        views later call `has_object_permission`; list views must scope their
        querysets explicitly because DRF does not run object permission checks
        for every row.
        """
        action = self.get_action(request, view)
        if action is None:
            return self._deny_misconfigured(view)

        subject = subject_from_request(request)
        return self._resolve(
            may_attempt(subject, action),
            action,
            role=subject.role,
        )

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        action = self.get_action(request, view)
        if action is None:
            return self._deny_misconfigured(view)

        subject = subject_from_request(request)
        decision = authorize(
            subject,
            action,
            self.get_resource(request, view, obj),
        )
        return self._resolve(
            decision,
            action,
            role=subject.role,
        )

    # -- denial translation -------------------------------------------------

    def _resolve(
        self,
        decision: Decision,
        action: Action,
        *,
        role: str | None,
    ) -> bool:
        if decision.allowed:
            return True

        # DRF reads `self.message` and `self.code` from the permission instance
        # when building a 403. Permission objects are recreated per request, so
        # this mutable presentation state cannot leak across concurrent requests.
        self.message, self.code = _client_error_for(decision.reason)

        # Action, reason, and role are sufficient for diagnostics. Avoid user or
        # resource identifiers here; the correlation ID links this record to the
        # request while keeping metric-label cardinality bounded.
        metric_role = role if role is not None else AUTHZ_ROLE_ANONYMOUS

        fanid_authz_denied_total.labels(
            action=str(action),
            role=metric_role,
        ).inc()

        logger.warning(
            "authorization.denied",
            extra={
                "authz_action": str(action),
                "authz_reason": decision.reason.value,
                "authz_role": metric_role,
            },
        )
        return False

    def _deny_misconfigured(self, view: Any) -> bool:
        """
        Deny a view with no declared action and log it as a configuration error.

        Missing authorization configuration must fail closed rather than being
        interpreted as "no rule applies".
        """
        self.message = FORBIDDEN_MESSAGE
        self.code = FORBIDDEN_CODE
        logger.error(
            "authorization.misconfigured_view",
            extra={"authz_view": type(view).__name__},
        )
        return False


class ActionPermission(BasePolicyPermission):
    """
    Resolve the action from a ViewSet's `policy_actions` table.

    A missing entry is never implicit authorization. Resolution fails and the
    request is denied, preserving deny-by-default behavior.
    """

    def get_action(self, request: Any, view: Any) -> Action | None:
        table: Mapping[str, Action] = getattr(view, "policy_actions", {}) or {}
        viewset_action = getattr(view, "action", None)
        if viewset_action is not None and viewset_action in table:
            candidate = table[viewset_action]
            return candidate if isinstance(candidate, Action) else None
        return super().get_action(request, view)


class SelfResourcePermission(ActionPermission):
    """
    Resource owned by the subject through an explicit ownership attribute.

    `owner_lookup` defaults to `user_id`; subclasses may override it when the
    resource itself is the user. Explicit lookup names avoid guessing ownership
    from object types.
    """

    owner_lookup: ClassVar[str] = "user_id"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(owner_id=getattr(obj, self.owner_lookup, None))


class OrganizerResourcePermission(ActionPermission):
    """Resource attached to an organizer through `obj.organizer_id`."""

    organizer_lookup: ClassVar[str] = "organizer_id"

    def get_resource(self, request: Any, view: Any, obj: Any) -> Resource:
        return Resource(organizer_id=getattr(obj, self.organizer_lookup, None))


class MethodScopedActionPermission(SelfResourcePermission):
    """
    Resolve one of two actions for the same endpoint based on the HTTP method.

    `GET`, `HEAD`, and `OPTIONS` use the read action; all other methods use
    the write action.
    """

    read_action: ClassVar[Action | None] = None
    write_action: ClassVar[Action | None] = None

    def get_action(self, request: Any, view: Any) -> Action | None:
        safe = request.method in SAFE_METHODS
        attribute = "read_action" if safe else "write_action"
        action = getattr(view, attribute, None) or getattr(self, attribute, None)
        return action if isinstance(action, Action) else None


class SelfUserPermission(MethodScopedActionPermission):
    """Self-service permission when the resource itself is the User."""

    owner_lookup = "pk"
