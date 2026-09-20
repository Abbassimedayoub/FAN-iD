"""
The authorization policy: who may do what and under which conditions.

THIS FILE IS THE SOURCE OF TRUTH FOR AUTHORIZATION.

`Role.permissions` in the database is DESCRIPTIVE JSONB used for display in
administration interfaces, never for making authorization decisions. A policy
stored in the database can be changed without code review, tests, or a source
diff, which is exactly what authorization controls should avoid. Changes here
go through review and the policy test matrix.

The structure is `role -> action -> Grant`. A missing entry means DENY. There
is intentionally no explicit `DENY` effect, avoiding precedence rules between
allows and denies. The question "may this role do this?" therefore has a single,
unambiguous interpretation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from ..constants import ROLE_ADMIN, ROLE_FAN, ROLE_ORGANIZER, ROLE_SCANNER
from .actions import Action


class Scope(StrEnum):
    """ABAC scope: which resource instances a grant applies to."""

    #: No target resource instance, e.g. creation or collection-level action.
    NONE = "none"
    #: The resource must belong to the subject through `resource.owner_id`.
    SELF = "self"
    #: The resource must belong to the subject's organizer.
    OWN_ORGANIZER = "own_organizer"
    #: No instance restriction. Reserved for supervisory roles and justified
    #: explicitly in the policy table below.
    ANY = "any"


@dataclass(frozen=True, slots=True)
class Grant:
    """An allowed action together with its conditions."""

    scope: Scope
    #: Requires `auth_level >= AUTH_LEVEL_STEP_UP`. Reserved for actions whose
    #: abuse is irreversible or could enable account takeover.
    step_up: bool = False


# --------------------------------------------------------------------------
# Self-service: identical for all four roles by design.
# --------------------------------------------------------------------------
# Every authenticated human manages their own account regardless of role.
# This block is factored out so four copies cannot drift accidentally. The
# exhaustive test matrix still spells out expected permissions independently.
_SELF_SERVICE: Final[Mapping[Action, Grant]] = MappingProxyType(
    {
        Action.USER_READ_SELF: Grant(Scope.SELF),
        Action.USER_UPDATE_SELF: Grant(Scope.SELF),
        # Account deletion is irreversible and requires step-up verification.
        Action.USER_DELETE_SELF: Grant(Scope.SELF, step_up=True),
        Action.DEVICE_LIST_SELF: Grant(Scope.SELF),
        # Revoking the bound device can open the account to a new device, so it
        # requires fresh proof of identity rather than only a valid token.
        Action.DEVICE_REVOKE_SELF: Grant(Scope.SELF, step_up=True),
        Action.SESSION_LIST_SELF: Grant(Scope.SELF),
        # Revoking a session reduces access. Requiring step-up to sign out would
        # obstruct the useful response to token theft.
        Action.SESSION_REVOKE_SELF: Grant(Scope.SELF),
    }
)


def _with_self_service(specific: Mapping[Action, Grant]) -> Mapping[Action, Grant]:
    return MappingProxyType({**_SELF_SERVICE, **specific})


POLICY: Final[Mapping[str, Mapping[Action, Grant]]] = MappingProxyType(
    {
        # ------------------------------------------------------------------
        ROLE_FAN: _with_self_service(
            {
                # A fan may submit an organizer application.
                Action.ORGANIZER_CREATE: Grant(Scope.NONE),
            }
        ),
        # ------------------------------------------------------------------
        ROLE_ORGANIZER: _with_self_service(
            {
                # No ORGANIZER_CREATE: one account maps to one organizer.
                # Enforce the rule in policy instead of relying only on a
                # uniqueness violation that would surface as the wrong API error.
                Action.ORGANIZER_READ: Grant(Scope.OWN_ORGANIZER),
                Action.ORGANIZER_UPDATE: Grant(Scope.OWN_ORGANIZER),
                Action.SCANNER_INVITE: Grant(Scope.NONE),
                Action.SCANNER_READ: Grant(Scope.NONE),
                Action.SCANNER_REVOKE: Grant(Scope.NONE),
                Action.SCANNER_CREDENTIAL_RESET: Grant(Scope.NONE),
                # Organizer catalog. Approval is an additional actor-level
                # prerequisite enforced by IsApprovedOrganizer.
                Action.CATEGORY_READ: Grant(Scope.NONE),
                Action.CATEGORY_CREATE: Grant(Scope.NONE),
                Action.CATEGORY_DELETE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_CREATE: Grant(Scope.NONE),
                Action.EVENT_READ: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_UPDATE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_DELETE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_PUBLISH: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_ARCHIVE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_UNARCHIVE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_POSTPONE: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_SUSPEND: Grant(Scope.OWN_ORGANIZER),
                Action.EVENT_CANCEL: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_CREATE: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_READ: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_UPDATE: Grant(Scope.OWN_ORGANIZER),
                Action.TICKET_CATEGORY_DELETE: Grant(Scope.OWN_ORGANIZER),
            }
        ),
        # ------------------------------------------------------------------
        ROLE_SCANNER: _with_self_service(
            {
                Action.ORGANIZER_READ: Grant(Scope.OWN_ORGANIZER),
                # A scanner may read organizer context but not modify it.
                Action.TICKET_SCAN: Grant(Scope.OWN_ORGANIZER),
            }
        ),
        # ------------------------------------------------------------------
        ROLE_ADMIN: _with_self_service(
            {
                # `ANY` is justified because moderation requires access to
                # other users' organizer records. This is the only role with
                # that scope in this policy.
                Action.ORGANIZER_READ: Grant(Scope.ANY),
                Action.ORGANIZER_UPDATE: Grant(Scope.ANY),
                Action.ORGANIZER_APPROVE: Grant(Scope.ANY, step_up=True),
                Action.ORGANIZER_REJECT: Grant(Scope.ANY, step_up=True),
                Action.ORGANIZER_SUSPEND: Grant(Scope.ANY, step_up=True),
                # No TICKET_SCAN: separation of duties. If an administrator
                # needs scanning privileges, grant the SCANNER role explicitly
                # so that change is visible and auditable.
            }
        ),
    }
)
