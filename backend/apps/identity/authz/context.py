"""
Translate an incoming request into the pure authorization `Subject`.

This is the only module that knows both Django request objects and the policy
engine. Role resolution uses already-loaded identifiers and performs no extra
database query. Unknown role identifiers remain distinguishable from anonymous
subjects so diagnostics report the correct denial reason.
"""

from __future__ import annotations

import uuid
from typing import Any, Final

from ..constants import AUTH_LEVEL_PASSWORD, ROLE_IDS
from .subject import ANONYMOUS, Subject

#: Reverse UUID-to-role-name table built once at import time.
ROLE_NAMES_BY_ID: Final[dict[uuid.UUID, str]] = {role_id: name for name, role_id in ROLE_IDS.items()}

#: Sentinel used when role_id matches no known code role; it appears in no policy and grants nothing.
UNKNOWN_ROLE: Final = "__unknown__"


def _organizer_id_from(request: Any) -> uuid.UUID | None:
    """
    Read the organizer identifier from request context.

    The owning context installs this primitive before permission checks. Missing
    or malformed values become None so organizer-scoped authorization fails
    closed without adding a database lookup.
    """
    value = getattr(request, "organizer_id", None)
    return value if isinstance(value, uuid.UUID) else None


def _organizer_is_approved_from(request: Any) -> bool:
    """Read organizer approval from request context; only an explicit boolean True is accepted."""
    value = getattr(request, "organizer_approved", False)
    return value if isinstance(value, bool) else False


def subject_from_request(request: Any) -> Subject:
    """Build an authorization subject from the incoming request."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return ANONYMOUS

    # role_id may come from a real user or a test double. Unexpected values map to
    # UNKNOWN_ROLE and therefore grant no permissions instead of raising.
    # exception au milieu d un controle d autorisation.
    role_id: Any = getattr(user, "role_id", None)
    role = ROLE_NAMES_BY_ID.get(role_id, UNKNOWN_ROLE) if isinstance(role_id, uuid.UUID) else UNKNOWN_ROLE

    # Treat anonymized accounts as inactive even while old tokens still exist.
    is_active = bool(getattr(user, "is_active", False)) and getattr(user, "anonymized_at", None) is None

    return Subject(
        user_id=user.pk,
        role=role,
        is_active=is_active,
        # Missing authentication-level context defaults to the lowest level so
        # incomplete requests cannot gain step-up permissions.
        auth_level=int(getattr(request, "auth_level", AUTH_LEVEL_PASSWORD)),
        organizer_id=_organizer_id_from(request),
        organizer_is_approved=_organizer_is_approved_from(request),
    )
