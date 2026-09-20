"""
The result of an authorization decision.

Two opposing requirements meet here:

- OPERATIONS needs to know WHY access was denied, otherwise a legitimate denial
  and a configuration bug look the same in logs.
- The CLIENT must learn nothing more than "no". Distinguishing "you do not have
  the role" from "this is not your resource" turns the API into an existence
  oracle: an attacker could enumerate identifiers by reading error codes
  without ever obtaining the underlying data.

Hence the separation: `Reason` is an internal code for logs and metrics; it is
never returned to the client as-is. The DRF adapter (`permissions.py`)
translates denials to opaque `FORBIDDEN`, except when the client can take a
specific action: `STEP_UP_REQUIRED` to provide stronger proof, and
`ORGANIZER_NOT_APPROVED` to wait for or obtain dossier approval. Neither code
reveals whether a resource exists.

`Reason` values are intentionally finite and contain no variable data because
they are used as Prometheus labels. A label containing a resource identifier or
error message would explode cardinality and could leak personal data into
monitoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Reason(StrEnum):
    """Stable decision reason with bounded cardinality and no variable data."""

    ALLOWED = "allowed"
    #: No authenticated subject.
    UNAUTHENTICATED = "unauthenticated"
    #: Disabled or anonymized account: no remaining rights, including self-access.
    INACTIVE_SUBJECT = "inactive_subject"
    #: Role unknown to the policy: corrupted data or role removed from code.
    UNKNOWN_ROLE = "unknown_role"
    #: Action missing from the catalog: typo or undeclared action.
    UNKNOWN_ACTION = "unknown_action"
    #: The role exists but this action is not granted to it.
    ROLE_NOT_GRANTED = "role_not_granted"
    #: The role is granted but the resource does not belong to the subject.
    NOT_OWNER = "not_owner"
    #: The resource lacks an attribute required by the rule.
    RESOURCE_ATTRIBUTE_MISSING = "resource_attribute_missing"
    #: The organizer exists but has not yet been approved.
    ORGANIZER_NOT_APPROVED = "organizer_not_approved"
    #: Rights are sufficient, but stronger authentication is required and missing.
    STEP_UP_REQUIRED = "step_up_required"


@dataclass(frozen=True, slots=True)
class Decision:
    """
    Authorization-engine verdict.

    `bool(decision)` raises an exception. A dataclass is truthy by default, so
    `if decision:` would silently authorize denials. Instead of relying on
    documentation, make that mistake impossible so it fails loudly rather than
    becoming a silent authorization flaw.
    """

    allowed: bool
    reason: Reason

    def __bool__(self) -> bool:
        raise TypeError(
            "Une Decision ne se teste pas par sa verite : ecrire `decision.allowed`. "
            "`if decision:` serait toujours vrai et autoriserait tous les refus."
        )

    def __post_init__(self) -> None:
        # Guard against inconsistent construction: `Decision(True,
        # Reason.NOT_OWNER)` would pass edge checks while making logs misleading.
        coherent = self.allowed is (self.reason is Reason.ALLOWED)
        if not coherent:
            raise ValueError(f"decision incoherente : allowed={self.allowed} reason={self.reason}")


#: Singleton positive verdict: an allowed decision has only one valid shape.
ALLOW = Decision(allowed=True, reason=Reason.ALLOWED)


def deny(reason: Reason) -> Decision:
    """Build a denial and reject `ALLOWED` as a denial reason."""
    if reason is Reason.ALLOWED:
        raise ValueError("un refus ne peut pas porter le motif ALLOWED")
    return Decision(allowed=False, reason=reason)
