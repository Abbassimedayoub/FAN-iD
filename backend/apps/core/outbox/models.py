"""
Tables `outbox_event` et `consumed_event` (§21/§22 master prompt, §3.1 Source B,
ADR-S-03). Garantissent l'invariant I-5 : aucun effet de bord validé n'est perdu.
"""
import uuid

from django.db import models


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        PUBLISHED = "PUBLISHED", "Publié"
        FAILED = "FAILED", "Échoué (sera retenté)"
        DEAD = "DEAD", "Mort (abandonné après 5 tentatives)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # sert d'event_id
    event_type = models.CharField(max_length=64)  # ex. "order.paid"
    event_version = models.PositiveSmallIntegerField(default=1)
    aggregate_type = models.CharField(max_length=40)
    aggregate_id = models.UUIDField()
    # Ordre global d'insertion (distinct de l'ordre par agrégat ci-dessous), alimenté
    # par une vraie séquence PostgreSQL (BIGSERIAL) posée en migration via RunSQL —
    # Django n'autorise pas un second AutoField non-PK sur un modèle (fields.E100),
    # d'où ce BigIntegerField() dont la valeur par défaut est `nextval(...)` côté SQL.
    sequence = models.BigIntegerField(editable=False, unique=True)
    payload = models.JSONField()
    correlation_id = models.CharField(max_length=40, null=True, blank=True)
    causation_id = models.UUIDField(null=True, blank=True)
    actor_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()  # backoff exponentiel — relais n'y touche pas avant cette date
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    occurred_at = models.DateTimeField()

    class Meta:
        app_label = "core"
        db_table = "outbox_event"
        constraints = [
            models.CheckConstraint(check=models.Q(attempts__gte=0), name="ck_outbox_attempts_nonneg"),
            models.CheckConstraint(
                check=models.Q(status__in=[s.value for s in Status]),
                name="ck_outbox_status_valid",
            ),
        ]
        indexes = [
            # Index du relais : ne couvre QUE la file active, pas les millions
            # d'événements déjà publiés (§21 master prompt).
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

    def __str__(self):
        return f"OutboxEvent({self.event_type}, status={self.status}, attempts={self.attempts})"


class ConsumedEvent(models.Model):
    """
    Déduplication côté consommateur (livraison Outbox *at-least-once*).

    La clé primaire composite EST le mécanisme de déduplication : un
    consommateur tente l'insertion en DÉBUT de traitement ; une IntegrityError
    signifie "déjà traité", il s'arrête sans effet (voir BaseConsumer).
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
