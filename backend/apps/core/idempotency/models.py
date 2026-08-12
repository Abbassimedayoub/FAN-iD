"""
Table `idempotency_record` (§20 master prompt / §3.1 Source B).

Garantit l'invariant I-5 (une requête rejouée ne produit qu'un effet).
L'INSERTION elle-même sert de verrou distribué via la contrainte
`UNIQUE(key, user_id)` : un `IntegrityError` à l'insertion signifie
"quelqu'un traite déjà cette clé" — jamais de SELECT-puis-INSERT (fenêtre de
course), voir `service.py`.
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="idempotency_records")
    endpoint = models.CharField(max_length=120)
    request_hash = models.CharField(max_length=64)  # SHA-256 hexdigest
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    # Sous-ensemble whitelisté d'en-têtes HTTP "clés" (Content-Type, Location,
    # Retry-After...) restitués lors d'un rejeu — voir
    # middleware.REPLAYABLE_RESPONSE_HEADERS. Jamais l'intégralité des
    # en-têtes originaux (Set-Cookie, X-Correlation-ID... ne sont jamais rejoués).
    response_headers = models.JSONField(null=True, blank=True, default=dict)
    locked_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        app_label = "core"  # rattaché aux migrations de l'app `core` (Source B §3.1 : core/migrations/0001_infrastructure.py)
        db_table = "idempotency_record"
        constraints = [
            models.UniqueConstraint(fields=["key", "user"], name="uq_idempotency_key_user"),
            models.CheckConstraint(
                check=models.Q(
    status__in=["IN_PROGRESS", "COMPLETED", "FAILED"]
),
                name="ck_idempotency_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["expires_at"], name="ix_idempotency_expires_at"),
        ]

    def __str__(self):
        return f"IdempotencyRecord({self.key}, user={self.user_id}, status={self.status})"
