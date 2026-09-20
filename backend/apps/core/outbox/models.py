"""
`outbox_event` and `consumed_event` tables.
They guarantee the invariant that no committed side effect is lost.
"""

import uuid

from django.db import models


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        PUBLISHED = "PUBLISHED", "Publié"
        FAILED = "FAILED", "Échoué (sera retenté)"
        DEAD = "DEAD", "Mort (abandonné après 5 tentatives)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # used as event_id
    event_type = models.CharField(max_length=64)  # e.g. "order.paid"
    event_version = models.PositiveSmallIntegerField(default=1)
    aggregate_type = models.CharField(max_length=40)
    aggregate_id = models.UUIDField()
    # Global insertion order, distinct from the per-aggregate ordering below.
    # Backed by a real PostgreSQL BIGSERIAL sequence created in the migration
    # with RunSQL. Django does not allow a second non-PK AutoField on a model
    # (fields.E100), hence this BigIntegerField whose SQL default is
    # `nextval(...)`.
    sequence = models.BigIntegerField(
        editable=False,
        unique=True,
        db_default=models.expressions.RawSQL(
            "nextval('outbox_event_sequence_seq')",
            params=[],
        ),
    )
    payload = models.JSONField()
    correlation_id = models.CharField(max_length=40, null=True, blank=True)
    causation_id = models.UUIDField(null=True, blank=True)
    actor_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()  # exponential backoff: relay waits until this timestamp
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    occurred_at = models.DateTimeField()

    class Meta:
        app_label = "core"
        db_table = "outbox_event"
        constraints = [
            models.CheckConstraint(condition=models.Q(attempts__gte=0), name="ck_outbox_attempts_nonneg"),
            models.CheckConstraint(
                condition=models.Q(status__in=["PENDING", "PUBLISHED", "FAILED", "DEAD"]),
                name="ck_outbox_status_valid",
            ),
        ]
        indexes = [
            # Relay index: covers ONLY the active queue, not already-published events.
            models.Index(
                fields=["status", "available_at"],
                name="ix_outbox_relay_queue",
                condition=models.Q(status__in=["PENDING", "FAILED"]),
            ),
            models.Index(
                fields=["aggregate_type", "aggregate_id", "sequence"],
                name="ix_outbox_aggregate_order",
            ),
            models.Index(
                fields=["status"],
                name="ix_outbox_dead",
                condition=models.Q(status="DEAD"),
            ),
        ]

    def __str__(self) -> str:
        return f"OutboxEvent({self.event_type}, status={self.status}, attempts={self.attempts})"


class ConsumedEvent(models.Model):
    """
    Consumer-side deduplication for at-least-once Outbox delivery.

    The composite key is the deduplication mechanism: a consumer attempts the
    insert at the START of processing. An IntegrityError means the event was
    already processed, so it stops without producing a side effect.
    """

    consumer_name = models.CharField(max_length=80)
    event_id = models.UUIDField()
    consumed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        db_table = "consumed_event"
        constraints = [
            models.UniqueConstraint(fields=["consumer_name", "event_id"], name="pk_consumed_event"),
        ]
        indexes = [
            models.Index(fields=["consumed_at"], name="ix_consumed_event_purge"),
        ]
