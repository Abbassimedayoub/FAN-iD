from __future__ import annotations

import logging
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.concurrency import versioned_update

from ..models import User

logger = logging.getLogger("fanid.identity")


class ProfileService:
    """Mise à jour optimiste du profil self-service."""

    @classmethod
    @transaction.atomic
    def update(
        cls,
        *,
        user_id: uuid.UUID,
        expected_version: int,
        changes: dict[str, Any],
    ) -> User:
        allowed = {"first_name", "last_name", "phone"}
        updates = {key: value for key, value in changes.items() if key in allowed}
        updates["updated_at"] = timezone.now()

        new_version = versioned_update(
            model=User,
            pk=user_id,
            expected_version=expected_version,
            updates=updates,
        )

        logger.info(
            "auth.profile.updated",
            extra={
                "user_id": str(user_id),
                "version": new_version,
            },
        )

        return User.objects.select_related("role").get(pk=user_id)
