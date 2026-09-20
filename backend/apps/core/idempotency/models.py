"""
Database model for idempotency records.

The unique `(key, user_id)` constraint makes the INSERT itself the distributed
lock. An `IntegrityError` means another request already owns that key.
"""

import uuid

from django.conf import settings
from django.db import models


class IdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        COMPLETED = "COMPLETED", "Terminé"
        FAILED = "FAILED", "Échoué"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=64)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="idempotency_records"
    )
    endpoint = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)  # SHA-256 hex digest
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    # Only a small allowlist of replay-safe HTTP response headers is stored.
    # Headers such as Set-Cookie and X-Correlation-ID are never replayed.
    response_headers = models.JSONField(null=True, blank=True, default=dict)
    locked_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        # This model is attached to the `core` app migrations.
        app_label = "core"
        db_table = "idempotency_record"
        constraints = [
            models.UniqueConstraint(fields=["key", "user"], name="uq_idempotency_key_user"),
            models.CheckConstraint(
                condition=models.Q(status__in=["IN_PROGRESS", "COMPLETED", "FAILED"]),
                name="ck_idempotency_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["expires_at"], name="ix_idempotency_expires_at"),
        ]

    def __str__(self) -> str:
        return f"IdempotencyRecord({self.key}, user={self.user_id}, status={self.status})"
