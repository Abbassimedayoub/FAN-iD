"""
Public interface of the `identity` context.

Everything crossing the context boundary goes through this module.
`import-linter` enforces that `apps.organizing` may import
`apps.identity.api` but no other identity internals.

The exported symbol list is therefore a CONTRACT. Adding a symbol is an
architectural decision, not a convenience shortcut.

This module contains no business logic beyond a single small write operation;
otherwise it only re-exports public identity primitives.
"""

from __future__ import annotations

import logging
import uuid

from .authz import Action, Resource, Subject, authorize, may_attempt
from .constants import ROLE_FAN, ROLE_IDS, ROLE_ORGANIZER
from .events import USER_LOGGED_IN, USER_PASSWORD_CHANGED, USER_PHONE_CHANGED, USER_PROFILE_UPDATED
from .models import User
from .permissions import (
    ActionPermission,
    IsApprovedOrganizer,
    MethodScopedActionPermission,
    OrganizerResourcePermission,
)
from .services.scanner_accounts import (
    create_invited_scanner_account,
    deactivate_scanner_account,
    derive_scanner_temporary_password,
    rotate_scanner_temporary_password,
)

logger = logging.getLogger("fanid.identity")

__all__ = [
    "Action",
    "ActionPermission",
    "IsApprovedOrganizer",
    "MethodScopedActionPermission",
    "OrganizerResourcePermission",
    "Resource",
    "Subject",
    "authorize",
    "USER_LOGGED_IN",
    "USER_PASSWORD_CHANGED",
    "USER_PROFILE_UPDATED",
    "USER_PHONE_CHANGED",
    "create_invited_scanner_account",
    "deactivate_scanner_account",
    "derive_scanner_temporary_password",
    "rotate_scanner_temporary_password",
    "resolve_fan_user_id_by_email",
    "grant_organizer_role",
    "may_attempt",
]


def resolve_fan_user_id_by_email(
    *,
    email: str,
) -> uuid.UUID | None:
    """Return the non-anonymized Fan account matching the email."""
    return (
        User.objects.filter(
            email__iexact=email.strip(),
            role_id=ROLE_IDS[ROLE_FAN],
            anonymized_at__isnull=True,
        )
        .values_list("pk", flat=True)
        .first()
    )


def grant_organizer_role(*, user_id: uuid.UUID) -> bool:
    """
    Assign the `ORGANIZER` role and return True when a row changed.

    Sessions are intentionally not revoked. Session re-validation reads the
    current `user.role_id` from the database on each request, while the role
    claim in an existing token does not authorize anything. The change therefore
    takes effect immediately server-side; only client display may remain stale
    until its next refresh.

    The role ID comes from the deterministic UUID table in `constants.py`, so
    no lookup against `identity_role` is needed.
    """
    changed = User.objects.filter(pk=user_id).update(role_id=ROLE_IDS[ROLE_ORGANIZER])
    logger.info("identity.role.granted", extra={"role": ROLE_ORGANIZER, "changed": bool(changed)})
    return bool(changed)
