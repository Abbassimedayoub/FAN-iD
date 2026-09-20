"""
Base models for the platform foundation.

Absolute rule: `core` does not depend on any business bounded context
(ADR-S-01, enforced by import-linter). These abstract classes are imported by
bounded contexts, never the other way around.
"""

import uuid
from typing import Any

from django.db import models


class UUIDModel(models.Model):
    """
    UUID v4 primary key instead of a sequential integer.

    Ticket QR codes expose ticket identifiers. Sequential identifiers would make
    enumeration trivial, so externally exposed resources inherit this model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Shared creation and update timestamps for business models."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class VersionedModel(models.Model):
    """
    Optimistic-locking support for low-contention resources.

    Used by resources mainly edited by humans, such as events, categories,
    products, and organizer validation state. High-contention purchase-path
    resources use `SELECT FOR UPDATE` at the service layer instead.

    The application service is responsible for comparing the expected version
    and returning `409 STALE_RESOURCE`; this model only stores and increments
    the version counter.
    """

    version = models.PositiveIntegerField(default=1)

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        # self.pk does not tell us whether the row already exists: all project
        # primary keys are UUIDs populated before the first INSERT. Django's
        # _state.adding flag is the reliable signal for INSERT versus UPDATE.
        is_update = not self._state.adding and not kwargs.get("force_insert")
        if is_update:
            self.version = models.F("version") + 1
        super().save(*args, **kwargs)
        if is_update:
            self.refresh_from_db(fields=["version"])


# Sprint 0 infrastructure tables live in dedicated submodules for readability,
# but still belong to the Django `core` app and its root migration. Importing
# them here makes them visible to `makemigrations`.
from .idempotency.models import IdempotencyRecord  # noqa: E402,F401
from .outbox.models import ConsumedEvent, OutboxEvent  # noqa: E402,F401
