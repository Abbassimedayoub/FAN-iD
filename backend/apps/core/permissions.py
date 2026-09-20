"""
Project-wide default permission.

`DenyAll` belongs in core because it is a framework safety guard rather than a
business authorization rule. Core can therefore provide the default without
depending on the identity context.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.permissions import BasePermission

logger = logging.getLogger("fanid.authz")


class DenyAll(BasePermission):
    """
    Unconditional denial used as `DEFAULT_PERMISSION_CLASSES`.

    Missing authorization configuration must fail closed. Public endpoints must
    therefore opt in explicitly with `permission_classes = [AllowAny]`.
    """

    def has_permission(self, request: Any, view: Any) -> bool:
        logger.error(
            "authorization.view_without_policy",
            extra={"authz_view": type(view).__name__},
        )
        return False

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        return False
