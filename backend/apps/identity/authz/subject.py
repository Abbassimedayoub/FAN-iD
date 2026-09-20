"""
Pure data structures representing the subject and resource of an authorization
decision.

They are frozen dataclasses with no Django dependency, keeping the policy engine
pure, fast to test exhaustively, and unable to trigger accidental database
queries during authorization.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Subject:
    """
    Request actor reduced to attributes relevant to authorization; frozen to prevent
    privilege-changing mutation.
    """

    user_id: uuid.UUID | None = None
    role: str | None = None
    is_active: bool = False
    # 1 = password, 2 = step-up verification. Default to the lowest level so incomplete context fails closed.
    auth_level: int = 0
    # Set for an organizer or scanner attached to an organizer.
    organizer_id: uuid.UUID | None = None
    # Primitive installed by the owning context; False by default so missing context never implies approval.
    organizer_is_approved: bool = False

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None and self.role is not None


#: Shared fallback subject for unauthenticated requests.
#: evite qu un appelant fabrique un anonyme legerement different — par exemple
#: Keep its state non-authorizing so no accidental permission path opens.
ANONYMOUS = Subject()


@dataclass(frozen=True, slots=True)
class Resource:
    """Target-resource attributes for ABAC; missing required attributes always fail closed."""

    owner_id: uuid.UUID | None = None
    organizer_id: uuid.UUID | None = None
    #: Resource state-machine value when applicable.
    #: Reserved for state-aware authorization without changing the engine signature.
    state: str | None = None
